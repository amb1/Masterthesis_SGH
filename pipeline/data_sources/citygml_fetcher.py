import os
import sys
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from core.config_manager import load_config, get_module_config
from core.project_paths import get_output_path, get_config_path
import pandas as pd
import uuid
from collections import defaultdict

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Konfiguriere Logger für detaillierteres Debugging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# XML Entity Resolver
class XMLResolver(etree.Resolver):
    def resolve(self, system_url, public_id, context):
        # Definiere häufig verwendete Entities
        entities = {
            'uuml': 'ü',
            'auml': 'ä',
            'ouml': 'ö',
            'szlig': 'ß',
            'Auml': 'Ä',
            'Ouml': 'Ö',
            'Uuml': 'Ü'
        }
        
        # Wenn es sich um eine bekannte Entity handelt, gib den entsprechenden Wert zurück
        entity_name = system_url.split(';')[0] if system_url and ';' in system_url else system_url
        if entity_name in entities:
            return self.resolve_string(f'"{entities[entity_name]}"', context)
            
        # Andernfalls normal weiterverarbeiten
        return None

class CityGMLConfigError(Exception):
    """Fehler bei der CityGML-Konfiguration"""
    pass

class CityGMLBuildingProcessor:
    """CityGML-spezifische Verarbeitung"""
    def __init__(self, config):
        """
        Initialisiert den CityGML-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        # Lade CityGML-spezifische Konfiguration
        citygml_config_path = Path(root_dir) / "config" / "citygml" / "config.yml"
        if not citygml_config_path.exists():
            raise FileNotFoundError(f"CityGML-Konfigurationsdatei nicht gefunden: {citygml_config_path}")
            
        self.config = load_config(citygml_config_path)
        self.logger = logging.getLogger(__name__)
        
        # Verwende Namespaces aus Konfiguration
        self.ns = self.config.get('namespaces', {})
        
        # Initialisiere Geometrie-Statistiken
        self.geometry_stats = {
            'success': 0,
            'failed': 0,
            'total_area': 0,
            'min_area': float('inf'),
            'max_area': 0
        }

    def _extract_building_footprint(self, building) -> Optional[Union[Polygon, MultiPolygon]]:
        """Extrahiert 2D-Footprint eines Gebäudes aus LoD1 oder LoD2 Geometrien."""
        try:
            # Sammle alle LinearRings
            linear_rings = building.findall('.//gml:LinearRing', namespaces=self.ns)
            if not linear_rings:
                self.logger.warning("⚠️ Keine LinearRings gefunden")
                return None

            polygons = []
            for linear_ring in linear_rings:
                pos_list = linear_ring.find('gml:posList', namespaces=self.ns)
                if pos_list is None or not pos_list.text:
                    continue

                # Verbesserte Fehlerbehandlung beim Parsen der Koordinaten
                try:
                    coords_raw = [float(x) for x in pos_list.text.strip().split()]
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Parsen der Koordinaten: {e} – Inhalt: {pos_list.text[:100]}...")
                    continue

                if len(coords_raw) % 3 != 0:
                    self.logger.warning(f"⚠️ Ungültige 3D-Koordinatenanzahl: {len(coords_raw)} (nicht durch 3 teilbar)")
                    continue

                coords_2d = [(coords_raw[i], coords_raw[i + 1]) for i in range(0, len(coords_raw), 3)]
                if coords_2d[0] != coords_2d[-1]:
                    self.logger.debug(f"Ring nicht geschlossen, füge Startpunkt ans Ende an: {coords_2d[0]}")
                    coords_2d.append(coords_2d[0])

                # Verbesserte Fehlerbehandlung bei der Polygon-Erstellung
                try:
                    polygon = Polygon(coords_2d)
                except Exception as e:
                    self.logger.error(f"❌ Polygon-Fehler (Koordinaten: {coords_2d[:2]}...): {e}")
                    continue

                # Validierung und Reparatur wenn konfiguriert
                try:
                    if not polygon.is_valid:
                        if self.config.get('geometry', {}).get('validation', {}).get('fix_invalid', True):
                            polygon = polygon.buffer(0)
                            if not polygon.is_valid:
                                self.logger.warning("⚠️ Polygon konnte nicht repariert werden")
                                continue
                        else:
                            self.logger.warning("⚠️ Ungültiges Polygon")
                            continue

                    # Prüfe Mindestfläche
                    min_area = self.config.get('geometry', {}).get('min_area', 1.0)
                    if polygon.area < min_area:
                        self.logger.warning(f"⚠️ Polygon zu klein ({polygon.area:.1f}m²), wird verworfen")
                        continue

                except Exception as e:
                    self.logger.error(f"❌ Fehler bei der Geometrievalidierung: {e}")
                    continue

                polygons.append(polygon)

            if not polygons:
                return None
            elif len(polygons) == 1:
                return polygons[0]
            else:
                # Erstelle MultiPolygon aus allen gültigen Polygonen
                try:
                    return MultiPolygon(polygons)
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Erstellen des MultiPolygons: {e}")
                    # Fallback: Gib das erste gültige Polygon zurück
                    return polygons[0]

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Extrahieren des Footprints: {str(e)}")
            return None

    def _extract_building_data(self, building: etree.Element) -> Optional[Dict[str, Any]]:
        """Extrahiert alle konfigurierten Attribute aus einem Gebäude"""
        try:
            attributes = {}
            field_stats = defaultdict(int)
            
            # Sammle alle Felder
            for field, field_config in self.config['citygml_fields'].items():
                try:
                    value = None
                    xpath = field_config.get('xpath')
                    field_type = field_config.get('type', 'str')
                    
                    if xpath:
                        # XPath-basierte Extraktion
                        if xpath.startswith('@'):
                            # Attribut-Extraktion
                            attr_name = xpath[1:]
                            if '{' in attr_name:
                                value = building.get(attr_name)
                            else:
                                value = building.get(attr_name)
                        else:
                            # Element-Extraktion
                            element = building.find(xpath, self.ns)
                            if element is not None:
                                value = element.text
                    
                    # Typ-Konvertierung
                    if value is not None:
                        try:
                            if field_type == 'float':
                                value = float(value)
                            elif field_type == 'int':
                                value = int(value)
                            field_stats[field] += 1
                        except (ValueError, TypeError):
                            self.logger.debug(f"⚠️ Konvertierung fehlgeschlagen für {field}: {value}")
                            value = None
                            
                    if value is not None:
                        attributes[field] = value
                        
                except Exception as e:
                    self.logger.debug(f"⚠️ Fehler bei Extraktion von {field}: {str(e)}")
                
            # Wenn collect_all_fields aktiv ist, ignoriere required_fields
            if self.config.get('collect_all_fields', False):
                return attributes
            
            # Prüfe ob alle Pflichtfelder vorhanden sind
            required_fields = self.config.get('required_fields', [])
            if required_fields:
                missing_fields = [f for f in required_fields if f not in attributes]
                if missing_fields:
                    self.logger.error(f"❌ Fehlende Pflichtfelder: {missing_fields}")
                    return None
                
            return attributes
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Gebäudeverarbeitung: {str(e)}")
            return None

    def process_citygml(self, citygml_path):
        """Verarbeitet CityGML und erstellt Basis-GeoDataFrame"""
        try:
            self.logger.info(f"Verarbeite CityGML: {Path(citygml_path).name}")
            
            tree = etree.parse(citygml_path)
            root = tree.getroot()
            buildings = root.findall('.//bldg:Building', self.ns)
            
            self.logger.info(f"=== Starte Verarbeitung von {len(buildings)} Gebäuden ===")
            
            building_data = []
            geometries = []
            field_stats = defaultdict(int)
            
            # Erweiterte Statistiken
            stats = {
                'total': len(buildings),
                'success': 0,
                'failed': 0,
                'geometry': {
                    'success': 0,
                    'failed': 0,
                    'total_area': 0,
                    'min_area': float('inf'),
                    'max_area': 0,
                    'polygons': 0,
                    'multipolygons': 0
                },
                'attributes': {
                    'success': 0,
                    'failed': 0,
                    'field_coverage': defaultdict(int)
                },
                'lod': defaultdict(int)
            }
            
            for building in buildings:
                try:
                    # Extrahiere Geometrie
                    footprint = self._extract_building_footprint(building)
                    if footprint:
                        area = footprint.area
                        stats['geometry']['success'] += 1
                        stats['geometry']['total_area'] += area
                        stats['geometry']['min_area'] = min(stats['geometry']['min_area'], area)
                        stats['geometry']['max_area'] = max(stats['geometry']['max_area'], area)
                        
                        if isinstance(footprint, MultiPolygon):
                            stats['geometry']['multipolygons'] += 1
                        else:
                            stats['geometry']['polygons'] += 1
                        
                        # Bestimme LoD-Level
                        if building.find('.//bldg:lod2Solid', self.ns) is not None:
                            stats['lod']['LoD2'] += 1
                        elif building.find('.//bldg:lod1Solid', self.ns) is not None:
                            stats['lod']['LoD1'] += 1
                        
                        # Extrahiere Attribute
                        building_attrs = self._extract_building_data(building)
                        if building_attrs:
                            # Zähle vorhandene Felder
                            for field in building_attrs.keys():
                                stats['attributes']['field_coverage'][field] += 1
                                
                            building_data.append(building_attrs)
                            geometries.append(footprint)
                            stats['success'] += 1
                            stats['attributes']['success'] += 1
                        else:
                            stats['attributes']['failed'] += 1
                            if not self.config.get('collect_all_fields', False):
                                stats['failed'] += 1
                    else:
                        stats['geometry']['failed'] += 1
                        stats['failed'] += 1
                
                except Exception as e:
                    self.logger.error(f"❌ Fehler bei Gebäudeverarbeitung: {str(e)}")
                    stats['failed'] += 1
            
            # Ausgabe der erweiterten Statistiken
            self._print_extended_stats(stats)
            
            if not building_data:
                self.logger.warning("Keine Gebäudedaten extrahiert")
                return None
                
            # Erstelle GeoDataFrame
            buildings_gdf = gpd.GeoDataFrame(
                building_data,
                geometry=geometries,
                crs=self.config['geometry']['srs_name']
            )
            
            # Entferne Felder mit geringer Abdeckung
            if self.config.get('statistics', {}).get('collect_empty_fields', False):
                min_coverage = self.config.get('statistics', {}).get('min_coverage_threshold', 0.1)
                total_buildings = len(buildings)
                
                for field, count in stats['attributes']['field_coverage'].items():
                    coverage = count / total_buildings
                    if coverage < min_coverage:
                        self.logger.info(f"🗑️ Entferne Feld '{field}' (Abdeckung: {coverage:.1%})")
                        if field in buildings_gdf.columns:
                            buildings_gdf = buildings_gdf.drop(columns=[field])
            
            return buildings_gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei CityGML-Verarbeitung: {str(e)}")
            raise

    def _print_extended_stats(self, stats):
        """Gibt erweiterte Statistiken zur Verarbeitung aus"""
        self.logger.info("\n=== Verarbeitungsstatistik ===")
        self.logger.info(f"Gesamt: {stats['total']} Gebäude")
        self.logger.info(f"Erfolgreich: {stats['success']} Gebäude")
        self.logger.info(f"Fehlgeschlagen: {stats['failed']} Gebäude")
        
        self.logger.info("\n--- Geometrie ---")
        self.logger.info(f"Erfolgreich: {stats['geometry']['success']} Geometrien")
        self.logger.info(f"Fehlgeschlagen: {stats['geometry']['failed']} Geometrien")
        self.logger.info(f"Einfache Polygone: {stats['geometry']['polygons']}")
        self.logger.info(f"MultiPolygone: {stats['geometry']['multipolygons']}")
        
        if stats['geometry']['success'] > 0:
            avg_area = stats['geometry']['total_area'] / stats['geometry']['success']
            self.logger.info(f"Durchschnittliche Grundfläche: {avg_area:.1f}m²")
            self.logger.info(f"Kleinste Grundfläche: {stats['geometry']['min_area']:.1f}m²")
            self.logger.info(f"Größte Grundfläche: {stats['geometry']['max_area']:.1f}m²")
        
        self.logger.info("\n--- Attribute ---")
        self.logger.info(f"Erfolgreich: {stats['attributes']['success']} Datensätze")
        self.logger.info(f"Fehlgeschlagen: {stats['attributes']['failed']} Datensätze")
        
        # Feldabdeckung
        if stats['attributes']['field_coverage']:
            self.logger.info("\n--- Feldabdeckung ---")
            total_buildings = stats['total']
            for field, count in sorted(stats['attributes']['field_coverage'].items()):
                coverage = count / total_buildings
                self.logger.info(f"{field}: {count} ({coverage:.1%})")
        
        self.logger.info("\n--- LoD-Level ---")
        for lod, count in stats['lod'].items():
            self.logger.info(f"{lod}: {count} Gebäude")

def fetch_citygml_buildings(citygml_file: str, output_dir: str, config: Dict[str, Any]) -> Optional[gpd.GeoDataFrame]:
    """
    Liest CityGML-Datei und extrahiert Gebäudedaten in ein GeoDataFrame.
    
    Args:
        citygml_file: Pfad zur CityGML-Datei
        output_dir: Ausgabeverzeichnis für Zwischenergebnisse
        config: Globale Konfiguration
        
    Returns:
        GeoDataFrame mit Gebäudedaten oder None bei Fehler
    """
    try:
        # Lade die spezifische CityGML-Konfiguration
        citygml_config_path = config['data_source']['citygml'].get('config_file')
        if not citygml_config_path:
            raise CityGMLConfigError("Keine config_file in data_source.citygml konfiguriert")
            
        full_config_path = root_dir / citygml_config_path
        logger.info(f"📄 Lade CityGML-Konfiguration aus: {full_config_path}")
        
        if not full_config_path.exists():
            raise CityGMLConfigError(f"CityGML-Konfigurationsdatei nicht gefunden: {full_config_path}")
            
        citygml_config = load_config(full_config_path)
        
        # Debug-Ausgabe der geladenen Konfiguration
        logger.debug(f"🔍 CityGML-Konfiguration enthält Schlüssel: {list(citygml_config.keys())}")
        
        # Erstelle Processor mit der spezifischen CityGML-Konfiguration
        processor = CityGMLBuildingProcessor(citygml_config)
        
        # Verarbeite die CityGML-Datei
        gdf = processor.process_citygml(citygml_file)
        
        if gdf is not None and not gdf.empty:
            # Speichere Zwischenergebnis
            output_path = Path(output_dir) / "buildings_raw.gpkg"
            gdf.to_file(output_path, driver="GPKG")
            logger.info(f"✅ Gebäudedaten gespeichert in: {output_path}")
            return gdf
        else:
            logger.error("❌ Keine Gebäudedaten extrahiert")
            return None
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Verarbeiten der CityGML-Datei: {str(e)}")
        return None

if __name__ == "__main__":
    try:
        # Lade Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        config_path = root_dir / "config" / "global.yml"
        logger.info(f"📂 Suche Konfiguration in: {config_path}")
        config = load_config(config_path)
        
        if not config:
            logger.error("❌ Keine gültige Konfiguration gefunden")
            sys.exit(1)
        
        # Hole CityGML-Konfiguration
        citygml_config = config.get('data_source', {}).get('citygml', {})
        if not citygml_config:
            logger.error("❌ Keine CityGML-Konfiguration gefunden")
            sys.exit(1)
            
        # Konstruiere absoluten Pfad zur CityGML-Datei
        citygml_base_path = Path(citygml_config.get('base_path', ''))
        if citygml_base_path.parts[0] == 'local':
            citygml_base_path = citygml_base_path.relative_to('local')
        citygml_path = root_dir / citygml_base_path / citygml_config.get('default_file', '')
        
        # Konstruiere Output-Pfad
        output_dir = Path(config['project']['paths']['outputs']['citygml'])
        if output_dir.parts[0] == 'local':
            output_dir = output_dir.relative_to('local')
        output_dir = root_dir / output_dir
        
        if not citygml_path.exists():
            logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            sys.exit(1)
            
        if not output_dir.parent.exists():
            output_dir.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Ausgabeverzeichnis erstellt: {output_dir.parent}")
        
        # Extrahiere Gebäude mit der globalen Konfiguration
        buildings_gdf = fetch_citygml_buildings(str(citygml_path), str(output_dir), config)
        
        if buildings_gdf is not None:
            logger.info(f"✅ {len(buildings_gdf)} Gebäude extrahiert")
        else:
            logger.error("❌ Fehler beim Extrahieren der Gebäude")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fehler im Hauptprogramm: {str(e)}")
        sys.exit(1) 
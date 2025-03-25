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
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Erweiterte Namespace-Definition
        self.ns = {
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml',
            'core': 'http://www.opengis.net/citygml/1.0',
            'xal': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0',
            'gen': 'http://www.opengis.net/citygml/generics/1.0'  # Hinzugefügter gen-Namespace
        }
        
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
                    if self.config.get('geometry', {}).get('validation', {}).get('check_validity', False):
                        if not polygon.is_valid:
                            if self.config.get('geometry', {}).get('validation', {}).get('fix_invalid', False):
                                polygon = polygon.buffer(0)
                                if not polygon.is_valid:
                                    self.logger.warning("⚠️ Polygon konnte nicht repariert werden")
                                    continue
                            else:
                                self.logger.warning("⚠️ Ungültiges Polygon")
                                continue

                        # Prüfe Mindestfläche wenn konfiguriert
                        if self.config.get('geometry', {}).get('validation', {}).get('check_area', False):
                            min_area = self.config.get('geometry', {}).get('validation', {}).get('min_area', 1.0)
                            if polygon.area < min_area:
                                if self.config.get('geometry', {}).get('validation', {}).get('remove_small', False):
                                    self.logger.warning(f"⚠️ Polygon zu klein ({polygon.area:.1f}m²), wird verworfen")
                                    continue
                                else:
                                    self.logger.warning(f"⚠️ Polygon kleiner als Mindestfläche ({polygon.area:.1f}m²)")
                except Exception as e:
                    self.logger.error(f"❌ Fehler bei der Geometrievalidierung: {e}")
                    # Wenn Validierung fehlschlägt, nutze das unvalidierte Polygon
                    pass

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

    def _extract_building_data(self, building):
        """Extrahiert alle relevanten Attribute eines Gebäudes"""
        try:
            attributes = {}
            meta_fields = {}  # Speichert die Herkunft der Attribute
            
            building_id = building.get('{' + self.ns['gml'] + '}id', str(uuid.uuid4()))
            attributes['Name'] = building_id
            meta_fields['Name'] = 'extracted'
            
            missing_fields = []
            debug_mode = self.config.get('debug', False)  # Debug-Modus aus Config
            
            # Extrahiere konfigurierte Felder
            for field in self.config['required_fields']:
                field_conf = self.config['citygml_fields'].get(field, {})
                xpath = field_conf.get('xpath')
                field_type = field_conf.get('type')
                fallback = field_conf.get('fallback')

                if not xpath:
                    if debug_mode:
                        self.logger.debug(f"⚠️ Kein XPath für Feld {field} konfiguriert")
                    continue
                    
                value = None
                try:
                    # Spezielle Behandlung für komplexe Attribute
                    if field == 'year_of_construction':
                        for attr in building.findall('.//gen:stringAttribute', self.ns):
                            name_elem = attr.find('gen:name', self.ns)
                            val_elem = attr.find('gen:value', self.ns)
                            if name_elem is not None and name_elem.text and 'Baujahr' in name_elem.text:
                                value = val_elem.text.strip() if val_elem is not None and val_elem.text else None
                                meta_fields[field] = 'extracted'
                                break
                    
                    elif field == 'building_type':
                        for attr in building.findall('.//gen:stringAttribute', self.ns):
                            name_elem = attr.find('gen:name', self.ns)
                            val_elem = attr.find('gen:value', self.ns)
                            if name_elem is not None and name_elem.text and 'Nutzung' in name_elem.text:
                                value = val_elem.text.strip() if val_elem is not None and val_elem.text else None
                                meta_fields[field] = 'extracted'
                                break
                                
                    elif field == 'measured_height':
                        for attr in building.findall('.//gen:doubleAttribute', self.ns):
                            name_elem = attr.find('gen:name', self.ns)
                            val_elem = attr.find('gen:value', self.ns)
                            if name_elem is not None and name_elem.text and 'Gebäudehöhe' in name_elem.text:
                                value = val_elem.text.strip() if val_elem is not None and val_elem.text else None
                                meta_fields[field] = 'extracted'
                                break
                    
                    else:
                        # Standardverarbeitung für einfache XPath-Ausdrücke
                        if xpath.startswith('@'):
                            # Attribut-Extraktion
                            attr_name = xpath[1:]
                            if ':' in attr_name:
                                ns, attr = attr_name.split(':')
                                attr_name = '{' + self.ns[ns] + '}' + attr
                            value = building.get(attr_name)
                            if value is not None:
                                meta_fields[field] = 'extracted'
                        else:
                            # Element-Extraktion mit direkter Namespace-Verwendung
                            element = building.find(f'.//{xpath}', self.ns)
                            if element is not None:
                                value = element.text.strip() if element.text else None
                                if value is not None:
                                    meta_fields[field] = 'extracted'

                    # Wenn None, auf fallback setzen
                    if value is None and fallback is not None:
                        value = fallback
                        meta_fields[field] = 'fallback'
                        if debug_mode:
                            self.logger.debug(f"⬇️ Fallback-Wert {fallback} für Feld {field} verwendet")

                    # Typkonvertierung
                    if value is not None and field_type:
                        try:
                            if field_type == "float":
                                value = float(value)
                            elif field_type == "int":
                                value = int(value)
                            elif field_type == "str":
                                value = str(value)
                        except ValueError:
                            if debug_mode:
                                self.logger.debug(f"⚠️ Typkonvertierung fehlgeschlagen für Feld {field}: {value}")
                            if fallback is not None:
                                value = fallback
                                meta_fields[field] = 'fallback_after_conversion_error'
                            
                except Exception as e:
                    if debug_mode:
                        self.logger.debug(f"⚠️ Fehler bei Extraktion von Feld {field}: {str(e)}")
                    missing_fields.append(field)
                    meta_fields[field] = 'missing'
                    continue

                attributes[field] = value
                if field not in meta_fields:
                    meta_fields[field] = 'missing' if value is None else 'extracted'

            if missing_fields and debug_mode:
                self.logger.debug(f"ℹ️ Fehlende Pflichtfelder für Gebäude {building_id}: {', '.join(missing_fields)}")

            # Füge Metadaten hinzu
            attributes['_meta'] = meta_fields
            return attributes

        except Exception as e:
            self.logger.error(f"❌ Fehler bei Attributextraktion für Gebäude: {str(e)}")
            raise

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
                    'missing_fields': defaultdict(int)
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
                        
                        # Extrahiere Attribute nur für gültige Geometrien
                        building_attrs = self._extract_building_data(building)
                        if building_attrs:
                            stats['attributes']['success'] += 1
                            building_data.append(building_attrs)
                            geometries.append(footprint)
                            stats['success'] += 1
                        else:
                            stats['attributes']['failed'] += 1
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
                
            # Erstelle GeoDataFrame mit korrektem CRS
            buildings_gdf = gpd.GeoDataFrame(
                building_data,
                geometry=geometries,
                crs=self.config['geometry']['srs_name']
            )
            
            # Sicherer Zugriff auf Geometrie-Vereinfachungsoptionen
            output_options = self.config.get('output', {}).get('geojson', {}).get('options', {})
            tolerance = output_options.get('simplify_tolerance')
            
            if tolerance:
                self.logger.info(f"ℹ️ Vereinfache Geometrien mit Toleranz {tolerance}")
                buildings_gdf.geometry = buildings_gdf.geometry.simplify(tolerance)
            
            # Optional: Metadaten in separate Spalten aufsplitten
            if self.config.get('split_meta_fields', False):
                meta_df = buildings_gdf['_meta'].apply(pd.Series)
                buildings_gdf = pd.concat([
                    buildings_gdf.drop(columns=['_meta']), 
                    meta_df.add_prefix('src_')
                ], axis=1)
            
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
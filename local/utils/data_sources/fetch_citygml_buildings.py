import os
import sys
from pathlib import Path
import logging
from typing import Dict, Any, Optional
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

# Konfiguriere Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
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

class CityGMLBuildingProcessor:
    """Extrahiert Gebäudedaten aus CityGML-Dateien"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den CityGML Building Processor.
        
        Args:
            config (dict): Konfiguration mit CityGML-Namespaces
        """
        self.config = config
        self.ns = config.get('citygml', {}).get('namespaces', {})
        
        # Namespace-Mapping für verschiedene CityGML-Versionen
        self.namespace_mapping = {
            '1.0': {
                'bldg': 'http://www.opengis.net/citygml/building/1.0',
                'gml': 'http://www.opengis.net/gml',
                'gen': 'http://www.opengis.net/citygml/generics/1.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            },
            '2.0': {
                'bldg': 'http://www.opengis.net/citygml/building/2.0',
                'gml': 'http://www.opengis.net/gml',
                'gen': 'http://www.opengis.net/citygml/generics/2.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            },
            '3.0': {
                'bldg': 'http://www.opengis.net/citygml/building/3.0',
                'gml': 'http://www.opengis.net/gml/3.2',
                'gen': 'http://www.opengis.net/citygml/generics/3.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            }
        }
    
    def _detect_citygml_version(self, root: etree.Element) -> str:
        """Erkennt die CityGML-Version aus dem Root-Element.
        
        Args:
            root (etree.Element): Das Root-Element des CityGML-Dokuments
            
        Returns:
            str: Die erkannte CityGML-Version
        """
        try:
            # Extrahiere alle Namespaces
            self.ns = {k: v for k, v in root.nsmap.items() if k is not None}
            
            # Bestimme Version basierend auf Namespaces
            for ns in self.ns.values():
                if "citygml/3.0" in ns:
                    return "3.0"
                elif "citygml/2.0" in ns:
                    return "2.0"
                elif "citygml/1.0" in ns:
                    return "1.0"
            
            return "1.0"
            
        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der CityGML-Version-Erkennung: {str(e)}")
            return "1.0"
            
    def _extract_geometry(self, building: etree.Element) -> Optional[Polygon]:
        """Extrahiert die Gebäudegeometrie.
        
        Args:
            building (etree.Element): Das Gebäude-Element
            
        Returns:
            Optional[Polygon]: Die Gebäudegeometrie oder None
        """
        try:
            # LOD-spezifische Geometrie-Pfade
            lod_paths = {
                0: [
                    './/bldg:lod0FootPrint//gml:posList',
                    './/bldg:lod0RoofEdge//gml:posList',
                    './/bldg:lod0FootPrint//gml:coordinates',
                    './/bldg:lod0RoofEdge//gml:coordinates'
                ],
                1: [
                    './/bldg:lod1Solid//gml:posList',
                    './/bldg:lod1MultiSurface//gml:posList',
                    './/bldg:lod1Solid//gml:coordinates',
                    './/bldg:lod1MultiSurface//gml:coordinates'
                ],
                2: [
                    './/bldg:lod2Solid//gml:posList',
                    './/bldg:lod2MultiSurface//gml:posList',
                    './/bldg:boundedBy//bldg:GroundSurface//gml:posList',
                    './/bldg:lod2Solid//gml:coordinates',
                    './/bldg:lod2MultiSurface//gml:coordinates',
                    './/bldg:boundedBy//bldg:GroundSurface//gml:coordinates'
                ]
            }
            
            # Suche in allen LODs nach Geometrien
            for lod in range(2, -1, -1):  # Von LOD2 bis LOD0
                for path in lod_paths.get(lod, []):
                    elements = building.findall(path, namespaces=self.ns)
                    
                    for element in elements:
                        try:
                            # Extrahiere Koordinaten
                            coords_text = element.text.strip()
                            coords = [float(x) for x in coords_text.split()]
                            
                            # Prüfe ob genug Koordinaten für ein Polygon
                            if len(coords) >= 6:  # Mindestens 3 Punkte
                                # Erstelle Koordinatenliste
                                coord_pairs = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
                                
                                # Stelle sicher, dass das Polygon geschlossen ist
                                if coord_pairs[0] != coord_pairs[-1]:
                                    coord_pairs.append(coord_pairs[0])
                                    
                                # Erstelle und validiere Polygon
                                polygon = Polygon(coord_pairs)
                                if not polygon.is_valid:
                                    polygon = polygon.buffer(0)  # Versuche Polygon zu reparieren
                                    logger.info(f"🔧 Polygon für LOD{lod} repariert")
                                
                                if polygon.is_valid:
                                    logger.info(f"✅ Gültige Geometrie in LOD{lod} gefunden")
                                    return polygon
                                
                        except (ValueError, IndexError) as e:
                            continue
            
            logger.warning("⚠️ Keine gültige Geometrie in allen LODs gefunden")
            return None

        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der Geometrieextraktion: {str(e)}")
            return None
            
    def _extract_generic_attributes(self, building: etree.Element) -> Dict[str, Any]:
        """Extrahiert alle generischen Attribute eines Gebäudes.
        
        Args:
            building (etree.Element): Das Gebäude-Element
            
        Returns:
            Dict[str, Any]: Dictionary mit allen gefundenen Attributen
        """
        attributes = {}
        
        try:
            # Extrahiere alle Attribute mit Werten
            for element in building.iter():
                # Überspringe Elemente ohne Text
                if element.text is None or not element.text.strip():
                    continue
                
                # Hole lokalen Namen ohne Namespace
                local_name = etree.QName(element).localname
                
                # Versuche den Wert zu konvertieren
                try:
                    # Versuche float Konvertierung
                    value = float(element.text)
                    # Wenn es eine ganze Zahl ist, konvertiere zu int
                    if value.is_integer():
                        value = int(value)
                except ValueError:
                    # Wenn keine Zahl, behalte String
                    value = element.text.strip()
                
                # Speichere Attribut
                if local_name not in ['id', 'geometry']:
                    attributes[local_name] = value
            
            return attributes
            
        except Exception as e:
            logger.warning(f"⚠️ Fehler beim Extrahieren der generischen Attribute: {str(e)}")
            return attributes

    def extract_buildings(self, citygml_path: str) -> Optional[gpd.GeoDataFrame]:
        """Extrahiert alle Gebäude aus einer CityGML-Datei.
        
        Args:
            citygml_path (str): Pfad zur CityGML-Datei
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit allen Gebäudeinformationen
        """
        try:
            # Erstelle Parser mit Entity-Resolver
            parser = etree.XMLParser(resolve_entities=True)
            resolver = XMLResolver()
            parser.resolvers.add(resolver)
            
            # Parse CityGML
            tree = etree.parse(citygml_path, parser=parser)
            root = tree.getroot()
            
            # Detektiere CityGML-Version und setze Namespaces
            version = self._detect_citygml_version(root)
            logger.info(f"📊 CityGML-Version: {version}")
            
            # Setze Namespaces basierend auf Version
            if version in self.namespace_mapping:
                self.ns = self.namespace_mapping[version]
            logger.info(f"🔍 Verwende Namespaces: {self.ns}")
            
            # Suche nach Gebäuden und BuildingParts
            buildings = root.findall('.//bldg:Building', namespaces=self.ns)
            building_parts = root.findall('.//bldg:BuildingPart', namespaces=self.ns)
            
            if not buildings and not building_parts:
                logger.warning("⚠️ Keine Gebäude oder BuildingParts gefunden")
                return None

            logger.info(f"✅ {len(buildings)} Gebäude und {len(building_parts)} BuildingParts gefunden")
            
            # Verarbeite gefundene Gebäude und BuildingParts
            processed_buildings = []
            
            # Verarbeite Hauptgebäude
            for building in buildings:
                try:
                    # Extrahiere Geometrie
                    geometry = self._extract_geometry(building)
                    if geometry is None:
                        continue
                        
                    # Extrahiere alle verfügbaren Attribute
                    building_data = {
                        'gml_id': building.get(f'{{{self.ns["gml"]}}}id'),
                        'geometry': geometry,
                        'type': 'Building'
                    }
                    
                    # Füge alle generischen Attribute hinzu
                    building_data.update(self._extract_generic_attributes(building))
                    
                    processed_buildings.append(building_data)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Fehler bei der Verarbeitung eines Gebäudes: {str(e)}")
                    continue
            
            # Verarbeite BuildingParts
            for part in building_parts:
                try:
                    # Extrahiere Geometrie
                    geometry = self._extract_geometry(part)
                    if geometry is None:
                        continue
                        
                    # Finde Parent-Building ID
                    parent = part.getparent()
                    parent_id = parent.get(f'{{{self.ns["gml"]}}}id') if parent is not None else None
                    
                    # Extrahiere alle verfügbaren Attribute
                    part_data = {
                        'gml_id': part.get(f'{{{self.ns["gml"]}}}id'),
                        'parent_id': parent_id,
                        'geometry': geometry,
                        'type': 'BuildingPart'
                    }
                    
                    # Füge alle generischen Attribute hinzu
                    part_data.update(self._extract_generic_attributes(part))
                    
                    processed_buildings.append(part_data)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Fehler bei der Verarbeitung eines BuildingParts: {str(e)}")
                    continue
            
            if not processed_buildings:
                logger.error("❌ Keine Gebäude erfolgreich verarbeitet")
                return None

            # Erstelle GeoDataFrame
            gdf = gpd.GeoDataFrame(processed_buildings)
            
            # Setze CRS wenn in Konfiguration vorhanden
            if 'crs' in self.config:
                gdf.set_crs(self.config['crs'], inplace=True)
            
            logger.info(f"✅ GeoDataFrame mit {len(gdf)} Gebäuden/BuildingParts erstellt")
            return gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Verarbeiten der CityGML-Datei: {str(e)}")
            return None

def fetch_citygml_buildings(citygml_path: str, config: Dict[str, Any]) -> Optional[gpd.GeoDataFrame]:
    """Hauptfunktion zum Extrahieren von Gebäuden aus CityGML.
    
    Args:
        citygml_path (str): Pfad zur CityGML-Datei
        config (dict): Konfiguration mit CityGML-Namespaces und CRS
        
    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame mit allen Gebäudeinformationen
    """
    try:
        # Erstelle Processor
        processor = CityGMLBuildingProcessor(config)
        
        # Extrahiere Gebäude
        buildings_gdf = processor.extract_buildings(citygml_path)
        
        return buildings_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Extrahieren der Gebäude: {str(e)}")
        return None

if __name__ == "__main__":
    # Beispielaufruf
    from utils.data_processing.config_loader import load_config

    # Lade Konfiguration
    config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "project_config.yml"
    config = load_config(config_path)
    
    if not config:
        logger.error("❌ Keine gültige Konfiguration gefunden")
        sys.exit(1)
        
    # Erstelle Basiskonfiguration
    base_config = {
        'crs': config.get('project', {}).get('crs', "EPSG:31256"),
        'citygml': config.get('data_source', {}).get('citygml', {})
    }
    
    # Verarbeite CityGML-Datei
    citygml_path = Path(__file__).resolve().parent.parent.parent / "data" / "inputs" / "citygml" / "099082.gml"
    
    if not citygml_path.exists():
        logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
        sys.exit(1)
    
    # Extrahiere Gebäude
    buildings_gdf = fetch_citygml_buildings(str(citygml_path), base_config)
    
    if buildings_gdf is not None:
        # Speichere Ergebnisse
        output_path = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "citygml" / "buildings_raw.geojson"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buildings_gdf.to_file(output_path, driver='GeoJSON')
        logger.info(f"✅ Gebäude gespeichert nach: {output_path}")
    else:
        logger.error("❌ Keine Gebäude extrahiert") 
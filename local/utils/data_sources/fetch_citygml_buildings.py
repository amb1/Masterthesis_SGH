import os
import sys
from pathlib import Path
import logging
from typing import Dict, Any, Optional
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

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
        
        # Initialisiere Logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
        
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
            self.logger.warning(f"⚠️ Fehler bei der CityGML-Version-Erkennung: {str(e)}")
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
                                    self.logger.info(f"🔧 Polygon für LOD{lod} repariert")
                                
                                if polygon.is_valid:
                                    self.logger.info(f"✅ Gültige Geometrie in LOD{lod} gefunden")
                                    return polygon
                                
                        except (ValueError, IndexError) as e:
                            continue
            
            self.logger.warning("⚠️ Keine gültige Geometrie in allen LODs gefunden")
            return None

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrieextraktion: {str(e)}")
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
            # CityGML-spezifische Attribute
            attribute_paths = {
                'measuredHeight': ['.//bldg:measuredHeight', './/bldg:height'],
                'storeysAboveGround': ['.//bldg:storeysAboveGround', './/bldg:numberOfFloorsAboveGround'],
                'storeysBelowGround': ['.//bldg:storeysBelowGround', './/bldg:numberOfFloorsBelowGround'],
                'function': ['.//bldg:function', './/bldg:buildingFunction'],
                'usage': ['.//bldg:usage', './/bldg:buildingUsage'],
                'class': ['.//bldg:class', './/bldg:buildingClass'],
                'yearOfConstruction': ['.//bldg:yearOfConstruction', './/bldg:constructionYear'],
                'roofType': ['.//bldg:roofType', './/bldg:roofForm'],
                'materialOfWall': ['.//bldg:materialOfWall', './/bldg:wallMaterial'],
                'materialOfRoof': ['.//bldg:materialOfRoof', './/bldg:roofMaterial'],
                'storeyHeightsAboveGround': ['.//bldg:storeyHeightsAboveGround'],
                'storeyHeightsBelowGround': ['.//bldg:storeyHeightsBelowGround']
            }
            
            # Extrahiere spezifische Attribute
            for attr_name, xpaths in attribute_paths.items():
                for xpath in xpaths:
                    elements = building.findall(xpath, namespaces=self.ns)
                    if elements:
                        # Bei mehreren Werten, nehme den ersten nicht-leeren
                        for element in elements:
                            if element is not None and element.text and element.text.strip():
                                try:
                                    # Versuche Konvertierung zu float/int
                                    value = float(element.text)
                                    if value.is_integer() and attr_name not in ['measuredHeight']:
                                        value = int(value)
                                    attributes[attr_name] = value
                                    break
                                except ValueError:
                                    value = element.text.strip()
                                    attributes[attr_name] = value
                                    break
                        # Wenn wir einen Wert gefunden haben, brechen wir die XPath-Schleife ab
                        if attr_name in attributes:
                            break
            
            # Extrahiere generische Attribute
            generic_paths = {
                'stringAttribute': str,
                'intAttribute': int,
                'doubleAttribute': float,
                'dateAttribute': str,
                'uriAttribute': str,
                'measureAttribute': float
            }
            
            for attr_type, converter in generic_paths.items():
                xpath = f'.//gen:{attr_type}'
                generic_attributes = building.findall(xpath, namespaces=self.ns)
                
                for attr in generic_attributes:
                    try:
                        name = attr.get('name')
                        if name:
                            value_element = attr.find('.//gen:value', namespaces=self.ns)
                            if value_element is not None and value_element.text:
                                try:
                                    value = converter(value_element.text.strip())
                                    attributes[name] = value
                                except (ValueError, TypeError):
                                    self.logger.debug(f"⚠️ Konvertierungsfehler für Attribut {name}")
                    except Exception as e:
                        self.logger.debug(f"⚠️ Fehler beim Extrahieren des generischen Attributs: {str(e)}")
            
            # Extrahiere Address-Informationen
            address = building.find('.//bldg:address//xAL:AddressDetails', namespaces=self.ns)
            if address is not None:
                try:
                    # Straße
                    street = address.find('.//xAL:ThoroughfareName', namespaces=self.ns)
                    if street is not None and street.text:
                        attributes['street'] = street.text.strip()
                    
                    # Hausnummer
                    number = address.find('.//xAL:BuildingNumber', namespaces=self.ns)
                    if number is not None and number.text:
                        attributes['houseNumber'] = number.text.strip()
                    
                    # PLZ
                    postal = address.find('.//xAL:PostalCode', namespaces=self.ns)
                    if postal is not None and postal.text:
                        attributes['postalCode'] = postal.text.strip()
                    
                    # Stadt
                    city = address.find('.//xAL:LocalityName', namespaces=self.ns)
                    if city is not None and city.text:
                        attributes['city'] = city.text.strip()
                    
                    # Land
                    country = address.find('.//xAL:CountryName', namespaces=self.ns)
                    if country is not None and country.text:
                        attributes['country'] = country.text.strip()
                except Exception as e:
                    self.logger.debug(f"⚠️ Fehler beim Extrahieren der Adresse: {str(e)}")
            
            return attributes

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Extrahieren der Attribute: {str(e)}")
            return attributes

    def extract_buildings(self, citygml_path: str) -> Optional[gpd.GeoDataFrame]:
        """Extrahiert alle Gebäude aus einer CityGML-Datei.
        
        Args:
            citygml_path (str): Pfad zur CityGML-Datei
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit allen Gebäudeinformationen
        """
        try:
            # Parse CityGML und setze Namespaces
            parser = etree.XMLParser(resolve_entities=True)
            resolver = XMLResolver()
            parser.resolvers.add(resolver)
            tree = etree.parse(citygml_path, parser=parser)
            root = tree.getroot()
            
            version = self._detect_citygml_version(root)
            if version in self.namespace_mapping:
                self.ns = self.namespace_mapping[version]
            
            # Suche nach Gebäuden
            buildings = root.findall('.//bldg:Building', namespaces=self.ns)
            self.logger.info(f"🏢 {len(buildings)} Hauptgebäude gefunden")
            
            processed_buildings = []
            building_parts_count = 0
            
            # Verarbeite jedes Hauptgebäude
            for building in buildings:
                try:
                    # Extrahiere Basis-Attribute
                    building_data = {
                        'gml_id': building.get(f'{{{self.ns["gml"]}}}id'),
                        'building_parent_id': None,  # Hauptgebäude haben keine Parent-ID
                        'is_building_part': False
                    }
                    
                    # Extrahiere Geometrie
                    geometry = self._extract_geometry(building)
                    if geometry is None:
                        continue
                    
                    building_data['geometry'] = geometry
                    
                    # Extrahiere alle Attribute
                    building_data.update(self._extract_generic_attributes(building))
                    
                    # Suche nach BuildingParts
                    building_parts = building.findall('.//bldg:BuildingPart', namespaces=self.ns)
                    if building_parts:
                        building_parts_count += len(building_parts)
                        building_data['has_building_parts'] = True
                        building_data['building_parts_count'] = len(building_parts)
                        
                        # Verarbeite jedes BuildingPart
                        part_geometries = []
                        part_attributes = []
                        
                        for part in building_parts:
                            part_geom = self._extract_geometry(part)
                            if part_geom is not None:
                                part_geometries.append(part_geom)
                                
                            part_attrs = self._extract_generic_attributes(part)
                            if part_attrs:
                                part_attributes.append(part_attrs)
                        
                        # Füge BuildingPart-Geometrien zum Hauptgebäude hinzu
                        if part_geometries:
                            all_geometries = [geometry] + part_geometries
                            building_data['geometry'] = MultiPolygon(all_geometries)
                        
                        # Aggregiere BuildingPart-Attribute
                        for attr_dict in part_attributes:
                            for key, value in attr_dict.items():
                                if key not in building_data:
                                    building_data[f'part_{key}'] = value
                                elif isinstance(value, (int, float)):
                                    # Bei numerischen Werten: Summe oder Durchschnitt
                                    if key in ['measuredHeight', 'storeysAboveGround', 'storeysBelowGround']:
                                        building_data[f'part_{key}_avg'] = value
                                    else:
                                        building_data[f'part_{key}_sum'] = value
                
                    processed_buildings.append(building_data)
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Fehler bei der Verarbeitung eines Gebäudes: {str(e)}")
                    continue
            
            if not processed_buildings:
                self.logger.error("❌ Keine Gebäude erfolgreich verarbeitet")
                return None
            
            # Erstelle GeoDataFrame
            gdf = gpd.GeoDataFrame(processed_buildings)
            
            # Setze CRS wenn in Konfiguration vorhanden
            if 'crs' in self.config:
                gdf.set_crs(self.config['crs'], inplace=True)
            
            self.logger.info(f"✅ GeoDataFrame mit {len(gdf)} Gebäuden erstellt (inkl. {building_parts_count} BuildingParts)")
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Verarbeiten der CityGML-Datei: {str(e)}")
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
        # Speichere als GeoJSON
        output_path = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "citygml" / "buildings_raw.geojson"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        buildings_gdf.to_file(output_path, driver='GeoJSON')
        logger.info(f"✅ Gebäude gespeichert nach: {output_path}")
        
        # Speichere als Shapefile für QGIS
        shp_output_path = output_path.parent / "buildings_raw.shp"
        buildings_gdf.to_file(shp_output_path, driver='ESRI Shapefile')
        logger.info(f"✅ Gebäude als Shapefile gespeichert nach: {shp_output_path}")
    else:
        logger.error("❌ Keine Gebäude extrahiert") 
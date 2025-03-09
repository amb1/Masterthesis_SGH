import os
import sys
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union

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
            
    def _extract_geometry(self, building) -> Optional[Polygon]:
        """Extrahiert die Geometrie eines Gebäudes."""
        try:
            # Suche nach LOD2 Solid
            lod2_solid = building.find('.//bldg:lod2Solid', namespaces=self.ns)
            if lod2_solid is not None:
                return self._extract_solid_geometry(lod2_solid)
            
            # Suche nach LOD2 MultiSurface
            lod2_ms = building.find('.//bldg:lod2MultiSurface', namespaces=self.ns)
            if lod2_ms is not None:
                return self._extract_multisurface_geometry(lod2_ms)
            
            return None
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrieextraktion: {str(e)}")
            return None

    def _extract_solid_geometry(self, solid) -> Optional[Polygon]:
        """Extrahiert die Geometrie aus einem Solid."""
        try:
            # Finde alle Exterior Surfaces
            surfaces = solid.findall('.//{http://www.opengis.net/gml}exterior//{http://www.opengis.net/gml}Polygon', namespaces=self.ns)
            if not surfaces:
                return None
            
            # Extrahiere Koordinaten aus jeder Surface
            polygons = []
            for surface in surfaces:
                coords = self._extract_coordinates(surface)
                if coords and len(coords) >= 3:
                    # Skaliere die Koordinaten
                    scaled_coords = [(x/1000000, y/1000000) for x, y in coords]
                    polygons.append(Polygon(scaled_coords))
            
            if not polygons:
                return None
            
            # Vereinige alle Polygone
            union = unary_union(polygons)
            if isinstance(union, Polygon):
                return union
            elif isinstance(union, MultiPolygon):
                # Nimm das größte Polygon
                return max(union.geoms, key=lambda p: p.area)
            
            return None
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Solid-Geometrieextraktion: {str(e)}")
            return None

    def _extract_multisurface_geometry(self, multisurface) -> Optional[Polygon]:
        """Extrahiert die Geometrie aus einer MultiSurface."""
        try:
            # Finde alle Surface Members
            surfaces = multisurface.findall('.//{http://www.opengis.net/gml}surfaceMember//{http://www.opengis.net/gml}Polygon', namespaces=self.ns)
            if not surfaces:
                return None
            
            # Extrahiere Koordinaten aus jeder Surface
            polygons = []
            for surface in surfaces:
                coords = self._extract_coordinates(surface)
                if coords and len(coords) >= 3:
                    # Skaliere die Koordinaten
                    scaled_coords = [(x/1000000, y/1000000) for x, y in coords]
                    polygons.append(Polygon(scaled_coords))
            
            if not polygons:
                return None
            
            # Vereinige alle Polygone
            union = unary_union(polygons)
            if isinstance(union, Polygon):
                return union
            elif isinstance(union, MultiPolygon):
                # Nimm das größte Polygon
                return max(union.geoms, key=lambda p: p.area)
            
            return None
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der MultiSurface-Geometrieextraktion: {str(e)}")
            return None

    def _extract_coordinates(self, polygon) -> List[Tuple[float, float]]:
        """Extrahiert Koordinaten aus einem Polygon."""
        try:
            # Versuche zuerst posList
            pos_list = polygon.find('.//{http://www.opengis.net/gml}posList', namespaces=self.ns)
            if pos_list is not None and pos_list.text:
                coords = [float(x) for x in pos_list.text.split()]
                # Berücksichtige 3D-Koordinaten (x,y,z)
                return [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            
            # Versuche dann coordinates
            coordinates = polygon.find('.//{http://www.opengis.net/gml}coordinates', namespaces=self.ns)
            if coordinates is not None and coordinates.text:
                coord_list = []
                for coord in coordinates.text.split():
                    xyz = coord.split(',')
                    if len(xyz) >= 2:
                        coord_list.append((float(xyz[0]), float(xyz[1])))
                return coord_list
            
            # Versuche einzelne pos Elemente
            pos_elements = polygon.findall('.//{http://www.opengis.net/gml}pos', namespaces=self.ns)
            if pos_elements:
                coord_list = []
                for pos in pos_elements:
                    if pos.text:
                        coords = [float(x) for x in pos.text.split()]
                        if len(coords) >= 2:
                            coord_list.append((coords[0], coords[1]))
                return coord_list
            
            return []
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Koordinatenextraktion: {str(e)}")
            return []

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

    def _process_building(self, building) -> Optional[dict]:
        """Verarbeitet ein einzelnes Gebäude."""
        try:
            # Extrahiere Basis-Attribute
            building_data = {
                'gml_id': building.get(f'{{{self.ns["gml"]}}}id'),
                'building_parent_id': None,
                'is_building_part': False
            }
            
            # Extrahiere Geometrie
            geometry = self._extract_geometry(building)
            if geometry is None:
                return None
            
            building_data['geometry'] = geometry
            
            # Extrahiere Attribute
            building_data.update(self._extract_generic_attributes(building))
            
            # Verarbeite BuildingParts
            building_parts = building.findall('.//bldg:BuildingPart', namespaces=self.ns)
            if building_parts:
                building_data['has_building_parts'] = True
                building_data['building_parts_count'] = len(building_parts)
                
                # Sammle Geometrien und Attribute der BuildingParts
                part_geometries = []
                part_heights = []
                
                for part in building_parts:
                    part_geom = self._extract_geometry(part)
                    if part_geom is not None:
                        # Füge BuildingPart-Geometrie hinzu, auch wenn sie das Hauptgebäude überlappt
                        part_geometries.append(part_geom)
                    
                    part_attrs = self._extract_generic_attributes(part)
                    if 'measuredHeight' in part_attrs:
                        part_heights.append(part_attrs['measuredHeight'])
                
                # Füge BuildingPart-Geometrien hinzu
                if part_geometries:
                    all_geometries = [geometry] + part_geometries
                    # Vereinige überlappende Geometrien
                    union = unary_union(all_geometries)
                    if isinstance(union, Polygon):
                        building_data['geometry'] = union
                    else:
                        building_data['geometry'] = MultiPolygon(all_geometries)
                
                # Berechne durchschnittliche Höhe der BuildingParts
                if part_heights:
                    building_data['part_measuredHeight_avg'] = sum(part_heights) / len(part_heights)
            
            return building_data
        
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Verarbeitung eines Gebäudes: {str(e)}")
            return None

    def extract_buildings(self, citygml_path: str) -> Optional[gpd.GeoDataFrame]:
        """Extrahiert alle Gebäude aus einer CityGML-Datei."""
        try:
            # Parse CityGML file
            parser = etree.XMLParser(resolve_entities=False)
            tree = etree.parse(citygml_path, parser=parser)
            root = tree.getroot()
            self.ns = root.nsmap

            # Extrahiere CRS aus der CityGML-Datei
            envelope = root.find('.//{http://www.opengis.net/gml}Envelope', namespaces=self.ns)
            source_crs = None
            if envelope is not None:
                srs_name = envelope.get('srsName')
                if srs_name:
                    if 'EPSG' in srs_name.upper():
                        epsg_code = srs_name.upper().split('EPSG')[-1].strip(':')
                        try:
                            epsg_code = int(epsg_code)
                            source_crs = f"EPSG:{epsg_code}"
                        except ValueError:
                            self.logger.warning(f"⚠️ Ungültiger EPSG-Code in CityGML: {epsg_code}")
                    elif "31256" in srs_name:
                        source_crs = "EPSG:31256"
                    else:
                        self.logger.warning(f"⚠️ Unbekanntes CRS-Format: {srs_name}")

            if not source_crs:
                source_crs = self.config.get('crs', 'EPSG:31256')
                self.logger.info(f"ℹ️ Verwende Standard-CRS: {source_crs}")

            # Verarbeite Gebäude
            processed_buildings = []
            buildings = root.findall('.//{http://www.opengis.net/citygml/building/1.0}Building', namespaces=self.ns)
            self.logger.info(f"🔍 {len(buildings)} Gebäude gefunden")
            
            for building in buildings:
                building_data = self._process_building(building)
                if building_data:
                    processed_buildings.append(building_data)

            if not processed_buildings:
                self.logger.warning("❌ Keine Gebäude erfolgreich verarbeitet")
                return None

            # Erstelle GeoDataFrame
            gdf = gpd.GeoDataFrame(processed_buildings)
            
            # Setze CRS und transformiere zu WGS84
            gdf.set_crs(source_crs, inplace=True)
            self.logger.info(f"✅ CRS gesetzt auf: {source_crs}")
            
            # Transformiere zu WGS84 (EPSG:4326)
            gdf = gdf.to_crs('EPSG:4326')
            self.logger.info("✅ Koordinaten zu WGS84 (EPSG:4326) transformiert")

            # Validiere Geometrien
            invalid_geoms = gdf[~gdf.geometry.is_valid]
            if not invalid_geoms.empty:
                self.logger.warning(f"⚠️ {len(invalid_geoms)} ungültige Geometrien gefunden")
                gdf.geometry = gdf.geometry.buffer(0)  # Versuche Reparatur
                self.logger.info("✅ Geometrien repariert")

            # Speichere als GeoJSON und Shapefile
            output_dir = os.path.join(os.path.dirname(citygml_path), '..', 'outputs', 'citygml')
            os.makedirs(output_dir, exist_ok=True)
            
            gdf.to_file(os.path.join(output_dir, 'buildings_raw.geojson'), driver='GeoJSON')
            gdf.to_file(os.path.join(output_dir, 'buildings_raw.shp'))
            
            self.logger.info(f"✅ {len(gdf)} Gebäude extrahiert")
            return gdf

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Extrahieren der Gebäude: {str(e)}")
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
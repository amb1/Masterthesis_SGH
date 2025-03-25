import os
import sys
from pathlib import Path
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from lxml import etree
import geopandas as gpd
import numpy as np
import json
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from core.config_manager import load_config, get_module_config
from core.project_paths import get_output_path, get_config_path
import pandas as pd
import uuid
from collections import defaultdict
from py3dtiles import TileSet, Tile, B3dm, BatchTable

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

class GeometryValidationError(Exception):
    """Fehler bei der Geometrievalidierung"""
    pass

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
        
        # Prüfe ob es sich um eine Entity handelt
        if system_url.startswith('&') and system_url.endswith(';'):
            entity_name = system_url[1:-1]  # Entferne & und ;
            if entity_name in entities:
                return self.resolve_string(entities[entity_name], context)
                
        return None

class CityGMLConfigError(Exception):
    """Fehler in der CityGML-Konfiguration"""
    pass

class CityGMLBuildingProcessor:
    """Verarbeitet CityGML-Gebäude und extrahiert relevante Informationen"""
    
    def __init__(self, config):
        """
        Initialisiert den Prozessor.
        
        Args:
            config: Dictionary mit Konfiguration:
                fields: Dictionary mit Feldkonfigurationen:
                    name: Name des Feldes
                    type: Datentyp (string, float, int)
                    xpath: XPath-Ausdruck zum Extrahieren des Wertes
                    namespaces: Dictionary mit XML-Namespaces
                validation:
                    min_area: Minimale Fläche in m²
                    max_angle: Maximaler Winkel zwischen Normalen in Grad
        """
        self.config = config
        self.parser = etree.XMLParser(resolve_entities=False)
        self.parser.resolvers.add(XMLResolver())
        
        # Standard-Namespaces
        self.ns = {
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml',
            'gen': 'http://www.opengis.net/citygml/generics/1.0'
        }
        
        # Initialisiere Logger
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
    def _extract_building_footprint(self, building) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Extrahiert die Grundfläche eines Gebäudes.
        
        Args:
            building: XML-Element des Gebäudes
            
        Returns:
            Polygon/MultiPolygon der Grundfläche oder None bei Fehler
        """
        try:
            # Suche alle Grundflächen-Polygone
            footprints = []
            
            # Suche nach GroundSurface
            ground_surfaces = building.findall(
                ".//bldg:GroundSurface//gml:Polygon",
                namespaces=self.ns
            )
            
            # Wenn keine GroundSurface gefunden, suche nach allgemeinen Polygonen
            if not ground_surfaces:
                ground_surfaces = building.findall(
                    ".//gml:Polygon",
                    namespaces=self.ns
                )
            
            for polygon in ground_surfaces:
                # Extrahiere Koordinaten
                coords = []
                pos_lists = polygon.findall(
                    ".//gml:posList",
                    namespaces=self.ns
                )
                
                for pos_list in pos_lists:
                    # Konvertiere Koordinaten-String in Liste
                    values = [float(x) for x in pos_list.text.split()]
                    
                    # Gruppiere in 3D-Koordinaten
                    points = [(values[i], values[i+1]) for i in range(0, len(values), 3)]
                    
                    # Füge Punkte hinzu
                    coords.extend(points)
                    
                # Erstelle Polygon wenn genügend Punkte
                if len(coords) >= 3:
                    # Schließe Polygon falls nötig
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                        
                    # Erstelle und validiere Polygon
                    polygon = Polygon(coords)
                    if self._validate_polygon(polygon):
                        footprints.append(polygon)
            
            # Kombiniere Polygone
            if not footprints:
                return None
            elif len(footprints) == 1:
                return footprints[0]
            else:
                return MultiPolygon(footprints)
                
        except Exception as e:
            self.logger.warning(f"Fehler beim Extrahieren der Grundfläche: {str(e)}")
            return None
            
    def _validate_roof_coordinates(self, coords: np.ndarray, config: Dict[str, Any]) -> bool:
        """
        Validiert eine Dachfläche anhand ihrer Koordinaten.
        
        Args:
            coords: NumPy-Array mit 3D-Koordinaten
            config: Validierungskonfiguration
            
        Returns:
            True wenn gültig, False sonst
        """
        try:
            if coords.shape[0] < 3:
                self.logger.warning("Zu wenige Koordinaten für eine Dachfläche")
                return False

            # Fläche prüfen (über 2D-Projektion)
            xy_points = [(p[0], p[1]) for p in coords]
            polygon = Polygon(xy_points)
            area = polygon.area
            if area < config.get('min_area', 1.0):
                self.logger.warning(f"Polygon zu klein: {area:.1f}m² < {config.get('min_area', 1.0)}m²")
                return False

            # Winkel prüfen (Normale vs. Z-Achse)
            v1 = coords[1] - coords[0]
            v2 = coords[2] - coords[0]
            normal = np.cross(v1, v2)
            normal = normal / np.linalg.norm(normal)
            angle = np.arccos(np.abs(np.dot(normal, [0, 0, 1])))
            angle_deg = np.degrees(angle)
            if angle_deg > config.get('max_angle', 60):
                self.logger.warning(f"Dach zu steil: {angle_deg:.1f}° > {config.get('max_angle', 60)}°")
                return False

            return True

        except Exception as e:
            self.logger.warning(f"Fehler bei Dachflächen-Validierung: {str(e)}")
            return False

    def _extract_roof_surfaces(self, building) -> List[np.ndarray]:
        """
        Extrahiert Dachflächen aus einem CityGML-Building-Element.
        
        Args:
            building: XML-Element des Gebäudes
            
        Returns:
            Liste von Arrays mit 3D-Koordinaten der Dachflächen
        """
        try:
            # Finde alle RoofSurface-Elemente
            roof_surfaces = building.findall(
                ".//bldg:RoofSurface//gml:posList",
                namespaces=self.ns
            )
            
            # Extrahiere Koordinaten
            surfaces = []
            for surface in roof_surfaces:
                # Konvertiere String zu Koordinaten
                coords_str = surface.text.strip().split()
                coords = []
                for i in range(0, len(coords_str), 3):
                    x = float(coords_str[i])
                    y = float(coords_str[i + 1])
                    z = float(coords_str[i + 2])
                    coords.append([x, y, z])
                coords = np.array(coords)
                
                # Validiere Dachfläche mit den Koordinaten
                if self._validate_roof_coordinates(coords, self.config.get('validation', {})):
                    surfaces.append(coords)
                
            return surfaces
            
        except Exception as e:
            self.logger.warning(f"Fehler beim Extrahieren der Dachflächen: {str(e)}")
            return []
            
    def _validate_polygon(self, polygon: Polygon) -> bool:
        """
        Validiert ein Polygon.
        
        Args:
            polygon: Zu validierendes Polygon
            
        Returns:
            True wenn valid, False sonst
        """
        try:
            # Prüfe ob Polygon gültig ist
            if not polygon.is_valid:
                self.logger.warning("Ungültiges Polygon gefunden")
                return False
                
            # Prüfe Mindestfläche
            min_area = self.config.get('validation', {}).get('min_area', 1.0)
            if polygon.area < min_area:
                self.logger.warning(f"Polygon zu klein: {polygon.area:.1f}m² < {min_area}m²")
                return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"Fehler bei der Polygon-Validierung: {str(e)}")
            return False
            
    def _extract_field_value(self, building: etree.Element, field_config: Dict[str, Any]) -> Any:
        """
        Extrahiert einen Feldwert aus einem Gebäude.
        
        Args:
            building: XML-Element des Gebäudes
            field_config: Konfiguration des Feldes:
                type: Datentyp (string, float, int)
                xpath: XPath-Ausdruck
                namespaces: XML-Namespaces
                
        Returns:
            Extrahierter Wert oder None bei Fehler
        """
        try:
            # Extrahiere Wert mit XPath
            elements = building.xpath(
                field_config['xpath'],
                namespaces=field_config.get('namespaces', self.ns)
            )
            
            # Wenn kein Element gefunden
            if not elements:
                return None
                
            # Extrahiere Text aus Element
            element = elements[0]
            if isinstance(element, str):
                value = element
            else:
                value = element.text
                
            if not value:
                return None
                
            # Konvertiere in richtigen Datentyp
            if field_config['type'] == 'float':
                return float(value)
            elif field_config['type'] == 'int':
                return int(value)
            else:
                return str(value)
                
        except Exception as e:
            self.logger.warning(f"Fehler beim Extrahieren von Feldwert: {str(e)}")
            return None
            
    def _extract_building_attributes(self, building: etree.Element) -> Dict[str, Any]:
        """
        Extrahiert alle konfigurierten Attribute eines Gebäudes.
        
        Args:
            building: XML-Element des Gebäudes
            
        Returns:
            Dictionary mit Attributen
        """
        attributes = {}
        
        # Extrahiere konfigurierte Felder
        for field_name, field_config in self.config.get('fields', {}).items():
            value = self._extract_field_value(building, field_config)
            if value is not None:
                attributes[field_name] = value
                
        return attributes
        
    def process_citygml(self, citygml_path: Path) -> gpd.GeoDataFrame:
        """
        Verarbeitet eine CityGML-Datei und extrahiert Gebäudedaten.
        
        Args:
            citygml_path: Pfad zur CityGML-Datei
            
        Returns:
            GeoDataFrame mit Gebäudedaten oder leeres GeoDataFrame wenn keine gültigen Gebäude
        """
        try:
            self.logger.info(f"Lese CityGML-Datei {citygml_path}...")
            
            # Parse XML
            tree = etree.parse(str(citygml_path))
            root = tree.getroot()
            
            # Extrahiere Gebäude
            buildings = []
            for building in root.findall(".//bldg:Building", self.ns):
                try:
                    # Extrahiere Attribute
                    building_data = self._extract_building_data(building)
                    if building_data:
                        buildings.append(building_data)
                except Exception as e:
                    self.logger.warning(f"Fehler beim Verarbeiten eines Gebäudes: {str(e)}")
                    continue
                
            self.logger.info(f"{len(buildings)} Gebäude gefunden")
            
            if not buildings:
                self.logger.warning("Keine gültigen Gebäude gefunden")
                return gpd.GeoDataFrame(
                    columns=['building_id', 'height', 'geometry'],
                    crs="EPSG:31256"
                )
            
            # Erstelle GeoDataFrame
            gdf = gpd.GeoDataFrame(buildings)
            gdf.set_crs(epsg=31256, inplace=True)
            
            self.logger.info(f"{len(gdf)} Gebäude erfolgreich verarbeitet")
            return gdf
            
        except Exception as e:
            self.logger.error(f"Fehler beim Verarbeiten der CityGML: {str(e)}")
            return gpd.GeoDataFrame(
                columns=['building_id', 'height', 'geometry'],
                crs="EPSG:31256"
            )
            
    def _print_extended_stats(self, stats):
        """
        Gibt erweiterte Statistiken aus.
        
        Args:
            stats: Dictionary mit Statistiken
        """
        self.logger.info("\nErweiterte Statistiken:")
        self.logger.info("-" * 40)
        
        # Gebäudetypen
        if 'building_types' in stats:
            self.logger.info("\nGebäudetypen:")
            for type_name, count in stats['building_types'].items():
                self.logger.info(f"  {type_name}: {count}")
                
        # Höhenverteilung
        if 'height_stats' in stats:
            self.logger.info("\nHöhenverteilung:")
            for stat, value in stats['height_stats'].items():
                self.logger.info(f"  {stat}: {value:.2f}m")
                
        # Flächenverteilung
        if 'area_stats' in stats:
            self.logger.info("\nFlächenverteilung:")
            for stat, value in stats['area_stats'].items():
                self.logger.info(f"  {stat}: {value:.2f}m²")
                
        # Baujahre
        if 'year_stats' in stats:
            self.logger.info("\nBaujahre:")
            for stat, value in stats['year_stats'].items():
                self.logger.info(f"  {stat}: {value}")
                
        self.logger.info("-" * 40)
        
    def export_to_3dtiles(self, gdf: gpd.GeoDataFrame, output_path: Path) -> bool:
        """
        Exportiert die Gebäude als 3D Tiles.
        
        Args:
            gdf: GeoDataFrame mit Gebäuden
            output_path: Ausgabeverzeichnis
            
        Returns:
            True bei Erfolg, False bei Fehler
        """
        try:
            # Erstelle Ausgabeverzeichnis
            output_path.mkdir(parents=True, exist_ok=True)
            buildings_dir = output_path / "buildings"
            buildings_dir.mkdir(exist_ok=True)
            
            # Erstelle Tileset
            tileset = TileSet()
            
            # Erstelle Root-Tile
            root = Tile()
            root.geometric_error = 500.0  # TODO: Berechne basierend auf Datensatz
            root.refine = "ADD"
            
            # Berechne Bounding Box
            bounds = gdf.total_bounds
            root.bounding_volume = {
                "box": [
                    (bounds[0] + bounds[2]) / 2,  # center_x
                    (bounds[1] + bounds[3]) / 2,  # center_y
                    0,                            # center_z
                    (bounds[2] - bounds[0]) / 2,  # width/2
                    0, 0,
                    0,
                    (bounds[3] - bounds[1]) / 2,  # height/2
                    0,
                    0, 0,
                    50  # depth/2 (geschätzt)
                ]
            }
            
            # Erstelle Children für jedes Gebäude
            for idx, building in gdf.iterrows():
                # Erstelle B3DM
                b3dm_path = buildings_dir / f"{building.building_id}.b3dm"
                if not self._create_b3dm(building, b3dm_path):
                    continue
                    
                # Erstelle Child-Tile
                child = Tile()
                child.geometric_error = 0
                
                # Setze Bounding Box
                bounds = building.geometry.bounds
                child.bounding_volume = {
                    "box": [
                        (bounds[0] + bounds[2]) / 2,  # center_x
                        (bounds[1] + bounds[3]) / 2,  # center_y
                        building.height / 2,          # center_z
                        (bounds[2] - bounds[0]) / 2,  # width/2
                        0, 0,
                        0,
                        (bounds[3] - bounds[1]) / 2,  # height/2
                        0,
                        0, 0,
                        building.height / 2           # depth/2
                    ]
                }
                
                # Setze Content
                child.content = {
                    "uri": f"buildings/{building.building_id}.b3dm"
                }
                
                root.add_child(child)
                
            # Speichere Tileset
            tileset.root = root
            with open(output_path / "tileset.json", 'w') as f:
                json.dump(tileset.to_dict(), f, indent=2)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Fehler beim Export zu 3D Tiles: {str(e)}")
            return False
            
    def _save_as_citygml(self, gdf: gpd.GeoDataFrame, output_path: Path) -> None:
        """
        Speichert ein GeoDataFrame als CityGML-Datei.
        
        Args:
            gdf: GeoDataFrame mit Gebäudedaten
            output_path: Ausgabepfad für die CityGML-Datei
        """
        try:
            # Erstelle XML-Baum
            root = etree.Element(
                "CityModel",
                nsmap={
                    None: "http://www.opengis.net/citygml/1.0",
                    'bldg': "http://www.opengis.net/citygml/building/1.0",
                    'gml': "http://www.opengis.net/gml",
                    'gen': "http://www.opengis.net/citygml/generics/1.0"
                }
            )
            
            # Füge Gebäude hinzu
            for _, building in gdf.iterrows():
                # Erstelle Gebäude-Element
                building_elem = etree.SubElement(
                    root,
                    "cityObjectMember"
                )
                bldg_elem = etree.SubElement(
                    building_elem,
                    "{http://www.opengis.net/citygml/building/1.0}Building",
                    attrib={
                        "{http://www.opengis.net/gml}id": building['building_id']
                    }
                )
                
                # Füge Höhe hinzu
                height_elem = etree.SubElement(
                    bldg_elem,
                    "{http://www.opengis.net/citygml/generics/1.0}stringAttribute",
                    attrib={"name": "HoeheDach"}
                )
                value_elem = etree.SubElement(
                    height_elem,
                    "{http://www.opengis.net/citygml/generics/1.0}value"
                )
                value_elem.text = str(building['height'])
                
                # Füge Geometrie hinzu
                solid_elem = etree.SubElement(
                    bldg_elem,
                    "{http://www.opengis.net/citygml/building/1.0}lod2Solid"
                )
                solid = etree.SubElement(
                    solid_elem,
                    "{http://www.opengis.net/gml}Solid"
                )
                exterior = etree.SubElement(
                    solid,
                    "{http://www.opengis.net/gml}exterior"
                )
                comp_surface = etree.SubElement(
                    exterior,
                    "{http://www.opengis.net/gml}CompositeSurface"
                )
                
                # Füge Grundfläche hinzu
                footprint = building.geometry
                footprint_coords = np.array(footprint.exterior.coords)
                
                surface_member = etree.SubElement(
                    comp_surface,
                    "{http://www.opengis.net/gml}surfaceMember"
                )
                ground = etree.SubElement(
                    surface_member,
                    "{http://www.opengis.net/citygml/building/1.0}GroundSurface"
                )
                polygon = etree.SubElement(
                    ground,
                    "{http://www.opengis.net/gml}Polygon"
                )
                exterior_ring = etree.SubElement(
                    polygon,
                    "{http://www.opengis.net/gml}exterior"
                )
                linear_ring = etree.SubElement(
                    exterior_ring,
                    "{http://www.opengis.net/gml}LinearRing"
                )
                pos_list = etree.SubElement(
                    linear_ring,
                    "{http://www.opengis.net/gml}posList"
                )
                
                # Füge Koordinaten hinzu
                coords_text = []
                for x, y in footprint_coords:
                    coords_text.extend([str(x), str(y), "0"])
                pos_list.text = " ".join(coords_text)
                
                # Füge Dachflächen hinzu
                height = float(building['height'])
                center = np.mean(footprint_coords[:-1], axis=0)  # Ohne letzten Punkt (ist gleich erstem)
                
                # Berechne die Dachhöhe basierend auf einem flacheren Winkel
                max_angle = self.config.get('validation', {}).get('max_angle', 80.0)
                # Verwende einen deutlich kleineren Winkel für die Dachneigung
                roof_angle = max_angle * 0.25  # 25% des maximalen Winkels
                roof_height = height + (height * 0.5) * np.tan(np.radians(roof_angle))
                
                # Erzeuge die Dachflächen
                for i in range(len(footprint_coords) - 1):
                    surface_member = etree.SubElement(
                        comp_surface,
                        "{http://www.opengis.net/gml}surfaceMember"
                    )
                    roof = etree.SubElement(
                        surface_member,
                        "{http://www.opengis.net/citygml/building/1.0}RoofSurface"
                    )
                    polygon = etree.SubElement(
                        roof,
                        "{http://www.opengis.net/gml}Polygon"
                    )
                    exterior_ring = etree.SubElement(
                        polygon,
                        "{http://www.opengis.net/gml}exterior"
                    )
                    linear_ring = etree.SubElement(
                        exterior_ring,
                        "{http://www.opengis.net/gml}LinearRing"
                    )
                    pos_list = etree.SubElement(
                        linear_ring,
                        "{http://www.opengis.net/gml}posList"
                    )
                    
                    coords_text = []
                    # Füge die Eckpunkte des Daches hinzu
                    coords_text.extend([str(footprint_coords[i][0]), str(footprint_coords[i][1]), str(height)])
                    coords_text.extend([str(center[0]), str(center[1]), str(roof_height)])
                    coords_text.extend([str(footprint_coords[i+1][0]), str(footprint_coords[i+1][1]), str(height)])
                    coords_text.extend([str(footprint_coords[i][0]), str(footprint_coords[i][1]), str(height)])
                    pos_list.text = " ".join(coords_text)
            
            # Speichere XML
            tree = etree.ElementTree(root)
            tree.write(
                str(output_path),
                pretty_print=True,
                xml_declaration=True,
                encoding='utf-8'
            )
            
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern als CityGML: {str(e)}")
            
    def _extract_building_data(self, building) -> Optional[Dict]:
        """
        Extrahiert Gebäudedaten aus einem CityGML-Building-Element.
        
        Args:
            building: XML-Element des Gebäudes
            
        Returns:
            Dictionary mit Gebäudedaten oder None bei Fehler
        """
        try:
            # Extrahiere Grundfläche
            footprint = self._extract_building_footprint(building)
            if footprint is None:
                return None
            
            # Validiere Grundfläche
            if not self._validate_polygon(footprint):
                return None
            
            # Extrahiere Dachflächen
            roof_surfaces = self._extract_roof_surfaces(building)
            if not roof_surfaces:
                self.logger.warning("Keine gültigen Dachflächen gefunden")
                return None
            
            # Extrahiere Attribute
            building_id = building.get(f"{{{self.ns['gml']}}}id")
            if not building_id:
                building_id = str(uuid.uuid4())
            
            # Suche nach Höhenattribut
            height_elem = building.find(
                ".//gen:stringAttribute[@name='HoeheDach']/gen:value",
                namespaces=self.ns
            )
            height = 10.0  # Default-Höhe
            if height_elem is not None and height_elem.text:
                try:
                    height = float(height_elem.text)
                except ValueError:
                    self.logger.warning(f"Ungültige Höhe gefunden: {height_elem.text}")
            
            return {
                'building_id': building_id,
                'height': height,
                'geometry': footprint
            }
            
        except Exception as e:
            self.logger.warning(f"Fehler beim Extrahieren der Gebäudedaten: {str(e)}")
            return None

    def _get_coordinates(self, surface_element) -> List[Tuple[float, float, float]]:
        """
        Extrahiert 3D-Koordinaten aus einem Oberflächenelement.
        
        Args:
            surface_element: XML-Element der Oberfläche
            
        Returns:
            Liste von (x,y,z) Koordinaten-Tupeln
        """
        try:
            coords = []
            
            # Suche nach posList Elementen
            pos_lists = surface_element.findall(".//gml:posList", namespaces=self.ns)
            
            if pos_lists:
                for pos_list in pos_lists:
                    # Konvertiere String in Liste von Floats
                    values = [float(x) for x in pos_list.text.split()]
                    
                    # Prüfe ob Anzahl durch 3 teilbar
                    if len(values) % 3 != 0:
                        self.logger.warning(f"Ungültige Anzahl von Koordinaten: {len(values)}")
                        continue
                        
                    # Gruppiere in 3D-Koordinaten
                    for i in range(0, len(values), 3):
                        coords.append((values[i], values[i+1], values[i+2]))
            else:
                # Suche nach einzelnen pos Elementen
                pos_elements = surface_element.findall(".//gml:pos", namespaces=self.ns)
                for pos in pos_elements:
                    values = [float(x) for x in pos.text.split()]
                    if len(values) == 3:
                        coords.append((values[0], values[1], values[2]))
            
            # Prüfe ob genügend Koordinaten gefunden wurden
            if len(coords) < 3:
                self.logger.warning("Zu wenige Koordinaten gefunden")
                return []
                
            return coords
            
        except Exception as e:
            self.logger.warning(f"Fehler beim Extrahieren der Koordinaten: {str(e)}")
            return []

def fetch_citygml_buildings(citygml_file: str, output_dir: str, config: Dict[str, Any]) -> Optional[gpd.GeoDataFrame]:
    """
    Liest Gebäude aus einer CityGML-Datei.
    
    Args:
        citygml_file: Pfad zur CityGML-Datei
        output_dir: Ausgabeverzeichnis
        config: Konfiguration für den CityGML-Prozessor
        
    Returns:
        GeoDataFrame mit Gebäuden oder None bei Fehler
    """
    try:
        # Erstelle Prozessor
        processor = CityGMLBuildingProcessor(config)
        
        # Verarbeite CityGML
        buildings = processor.process_citygml(Path(citygml_file))
        if buildings is None:
            return None
            
        # Speichere als GeoPackage
        if output_dir:
            output_path = Path(output_dir) / "buildings.gpkg"
            buildings.to_file(output_path, driver="GPKG")
            logger.info(f"Gebäude gespeichert in {output_path}")
            
        return buildings
        
    except Exception as e:
        logger.error(f"Fehler beim Laden der CityGML: {str(e)}")
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
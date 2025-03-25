"""
CityGML-Geometrieprozessor für die Verarbeitung von Gebäudegeometrien.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Union
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from lxml import etree
import geopandas as gpd

class CityGMLGeometryProcessor:
    """Prozessor für CityGML-Geometrien."""
    
    def __init__(self, config: Dict[str, Any], namespaces: Dict[str, str]):
        """Initialisiert den Geometrie-Prozessor.
        
        Args:
            config: Dict[str, Any] - Geometrie-Konfiguration
            namespaces: Dict[str, str] - XML-Namespaces
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.namespaces = namespaces
        
        # Extrahiere Validierungsparameter
        self.validation = config.get('validation', {})
        self.min_area = float(self.validation.get('min_area', 10.0))
        
        # CRS aus der Konfiguration oder Standard
        self.crs = config.get('crs', 'EPSG:31256')
        
    def extract_building_footprint(self, building: etree.Element) -> Optional[Union[Polygon, MultiPolygon]]:
        """Extrahiert die Grundfläche eines Gebäudes.
        
        Args:
            building: etree.Element - XML-Element des Gebäudes
            
        Returns:
            Optional[Union[Polygon, MultiPolygon]]: Grundfläche oder None bei Fehler
        """
        try:
            # Suche alle Grundflächen-Polygone
            footprints = []
            
            # Suche nach GroundSurface
            ground_surfaces = building.findall(
                ".//bldg:GroundSurface//gml:Polygon",
                namespaces=self.namespaces
            )
            
            # Wenn keine GroundSurface gefunden, suche nach allgemeinen Polygonen
            if not ground_surfaces:
                ground_surfaces = building.findall(
                    ".//gml:Polygon",
                    namespaces=self.namespaces
                )
            
            for polygon in ground_surfaces:
                coords = self._extract_polygon_coordinates(polygon)
                if coords and len(coords) >= 3:
                    # Schließe Polygon falls nötig
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                        
                    # Erstelle und validiere Polygon
                    try:
                        polygon = Polygon(coords)
                        if self._validate_polygon(polygon):
                            footprints.append(polygon)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Ungültiges Polygon: {str(e)}")
                        continue
            
            # Kombiniere Polygone
            if not footprints:
                return None
            elif len(footprints) == 1:
                # Erstelle GeoDataFrame mit einem Polygon
                gdf = gpd.GeoDataFrame(geometry=[footprints[0]], crs=self.crs)
                return gdf.geometry[0]
            else:
                # Erstelle GeoDataFrame mit MultiPolygon
                multi_polygon = MultiPolygon(footprints)
                gdf = gpd.GeoDataFrame(geometry=[multi_polygon], crs=self.crs)
                return gdf.geometry[0]
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Extrahieren der Grundfläche: {str(e)}")
            return None
            
    def extract_roof_surfaces(self, building: etree.Element) -> List[np.ndarray]:
        """Extrahiert Dachflächen aus einem Gebäude.
        
        Args:
            building: etree.Element - XML-Element des Gebäudes
            
        Returns:
            List[np.ndarray]: Liste von Arrays mit 3D-Koordinaten der Dachflächen
        """
        try:
            # Finde alle RoofSurface-Elemente
            roof_surfaces = building.findall(
                ".//bldg:RoofSurface//gml:posList",
                namespaces=self.namespaces
            )
            
            # Extrahiere Koordinaten
            surfaces = []
            for surface in roof_surfaces:
                coords = self._extract_3d_coordinates(surface.text)
                if coords is not None and self._validate_roof_coordinates(coords):
                    surfaces.append(coords)
                
            return surfaces
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Extrahieren der Dachflächen: {str(e)}")
            return []
            
    def _extract_polygon_coordinates(self, polygon: etree.Element) -> List[Tuple[float, float]]:
        """Extrahiert 2D-Koordinaten aus einem Polygon.
        
        Args:
            polygon: etree.Element - XML-Element des Polygons
            
        Returns:
            List[Tuple[float, float]]: Liste von (x,y) Koordinaten
        """
        try:
            coords = []
            
            # Suche nach posList Elementen
            pos_lists = polygon.findall(".//gml:posList", namespaces=self.namespaces)
            
            if pos_lists:
                for pos_list in pos_lists:
                    values = [float(x) for x in pos_list.text.split()]
                    # Gruppiere in 3D-Koordinaten und projiziere auf 2D
                    for i in range(0, len(values), 3):
                        coords.append((values[i], values[i+1]))
            else:
                # Suche nach einzelnen pos Elementen
                pos_elements = polygon.findall(".//gml:pos", namespaces=self.namespaces)
                for pos in pos_elements:
                    values = [float(x) for x in pos.text.split()]
                    if len(values) >= 2:
                        coords.append((values[0], values[1]))
                        
            return coords
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Extrahieren der Koordinaten: {str(e)}")
            return []
            
    def _extract_3d_coordinates(self, coord_text: str) -> Optional[np.ndarray]:
        """Extrahiert 3D-Koordinaten aus einem Text.
        
        Args:
            coord_text: str - Koordinaten als Text
            
        Returns:
            Optional[np.ndarray]: Array mit 3D-Koordinaten oder None bei Fehler
        """
        try:
            values = [float(x) for x in coord_text.strip().split()]
            if len(values) % 3 != 0:
                return None
                
            coords = []
            for i in range(0, len(values), 3):
                coords.append([values[i], values[i+1], values[i+2]])
            return np.array(coords)
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Extrahieren der 3D-Koordinaten: {str(e)}")
            return None
            
    def _validate_polygon(self, polygon: Polygon) -> bool:
        """Validiert ein Polygon.
        
        Args:
            polygon: Polygon - Shapely-Polygon
            
        Returns:
            bool: True wenn das Polygon gültig ist
        """
        try:
            if not polygon.is_valid:
                if self.validation.get('fix_invalid', False):
                    polygon = polygon.buffer(0)
                    if not polygon.is_valid:
                        return False
                else:
                    return False
                    
            if self.validation.get('check_area', True):
                if polygon.area < self.min_area:
                    if self.validation.get('remove_small', False):
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Polygon-Validierung: {str(e)}")
            return False
            
    def _validate_roof_coordinates(self, coords: np.ndarray) -> bool:
        """Validiert Dachflächen-Koordinaten.
        
        Args:
            coords: np.ndarray - Array mit 3D-Koordinaten
            
        Returns:
            bool: True wenn die Koordinaten gültig sind
        """
        try:
            if len(coords) < 3:
                return False
                
            # Berechne Flächennormale
            v1 = coords[1] - coords[0]
            v2 = coords[2] - coords[0]
            normal = np.cross(v1, v2)
            normal = normal / np.linalg.norm(normal)
            
            # Prüfe Winkel zur Z-Achse
            angle = np.arccos(np.abs(normal[2])) * 180 / np.pi
            max_angle = self.validation.get('max_angle', 80)
            
            return angle <= max_angle
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Dachflächen-Validierung: {str(e)}")
            return False 
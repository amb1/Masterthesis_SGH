"""
Geometrieverarbeitung für OSM-Daten.
"""

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString
import logging
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)

class OSMGeometryProcessor:
    """Prozessor für OSM-Geometrien."""
    
    def __init__(self):
        """Initialisiert den Geometrieprozessor."""
        self.logger = logging.getLogger(__name__)
        
    def process_building_geometry(self, building_element: Dict[str, Any]) -> Optional[Polygon]:
        """
        Verarbeitet die Geometrie eines OSM-Gebäudes.
        
        Args:
            building_element: OSM-Gebäudeelement
            
        Returns:
            Polygon oder None bei Fehler
        """
        try:
            geometry = building_element.get('geometry')
            if not geometry or not hasattr(geometry, 'exterior'):
                return None
                
            return geometry
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrieverarbeitung: {str(e)}")
            return None
            
    def process_street_geometry(self, street_element: Dict[str, Any]) -> Optional[LineString]:
        """
        Verarbeitet die Geometrie einer OSM-Straße.
        
        Args:
            street_element: OSM-Straßenelement
            
        Returns:
            LineString oder None bei Fehler
        """
        try:
            geometry = street_element.get('geometry')
            if not geometry or not isinstance(geometry, LineString):
                return None
                
            return geometry
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrieverarbeitung: {str(e)}")
            return None
            
    def validate_building_geometry(self, geometry: Polygon) -> bool:
        """
        Validiert die Geometrie eines Gebäudes.
        
        Args:
            geometry: Gebäudegeometrie
            
        Returns:
            True wenn valid, sonst False
        """
        try:
            if not geometry.is_valid:
                return False
                
            if geometry.area <= 0:
                return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrievalidierung: {str(e)}")
            return False
            
    def validate_street_geometry(self, geometry: LineString) -> bool:
        """
        Validiert die Geometrie einer Straße.
        
        Args:
            geometry: Straßengeometrie
            
        Returns:
            True wenn valid, sonst False
        """
        try:
            if not geometry.is_valid:
                return False
                
            if geometry.length <= 0:
                return False
                
            return True
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Geometrievalidierung: {str(e)}")
            return False 
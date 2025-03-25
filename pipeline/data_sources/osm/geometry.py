"""
Geometrieverarbeitung für OSM-Daten.
"""

import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, LineString
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from shapely.ops import unary_union
from shapely.validation import explain_validity

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

class OSMGeometry:
    """Klasse für die Verarbeitung von OSM-Geometrien."""
    
    def __init__(self):
        """Initialisiert die OSM-Geometrie-Verarbeitung."""
        pass
        
    def validate_geometry(self, geometry: Union[Polygon, MultiPolygon]) -> bool:
        """
        Validiert eine Geometrie.
        
        Args:
            geometry: Die zu validierende Geometrie
            
        Returns:
            bool: True wenn valide, False sonst
        """
        try:
            if geometry.is_valid:
                return True
                
            reason = explain_validity(geometry)
            logger.warning(f"❌ Ungültige Geometrie: {reason}")
            return False
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrie-Validierung: {str(e)}")
            return False
            
    def simplify_geometry(self, geometry: Union[Polygon, MultiPolygon], 
                         tolerance: float = 0.1) -> Union[Polygon, MultiPolygon]:
        """
        Vereinfacht eine Geometrie.
        
        Args:
            geometry: Die zu vereinfachende Geometrie
            tolerance: Toleranz für die Vereinfachung
            
        Returns:
            Die vereinfachte Geometrie
        """
        try:
            return geometry.simplify(tolerance, preserve_topology=True)
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrie-Vereinfachung: {str(e)}")
            return geometry
            
    def extract_footprint(self, geometry: Union[Polygon, MultiPolygon]) -> Polygon:
        """
        Extrahiert den Grundriss aus einer Geometrie.
        
        Args:
            geometry: Die Quell-Geometrie
            
        Returns:
            Der extrahierte Grundriss als Polygon
        """
        try:
            if isinstance(geometry, Polygon):
                return geometry
                
            # Bei MultiPolygon: Größtes Polygon als Grundriss verwenden
            if isinstance(geometry, MultiPolygon):
                return max(geometry.geoms, key=lambda p: p.area)
                
            raise ValueError(f"Ungültiger Geometrie-Typ: {type(geometry)}")
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Grundriss-Extraktion: {str(e)}")
            if isinstance(geometry, MultiPolygon) and len(geometry.geoms) > 0:
                return geometry.geoms[0]
            return geometry
            
    def merge_geometries(self, geometries: List[Union[Polygon, MultiPolygon]]) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Verschmilzt mehrere Geometrien.
        
        Args:
            geometries: Liste der zu verschmelzenden Geometrien
            
        Returns:
            Optional[Union[Polygon, MultiPolygon]]: Die verschmolzene Geometrie
        """
        try:
            if not geometries:
                return None
                
            # Validiere alle Geometrien
            valid_geometries = [g for g in geometries if self.validate_geometry(g)]
            
            if not valid_geometries:
                return None
                
            # Verschmelze die Geometrien
            return unary_union(valid_geometries)
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Verschmelzen der Geometrien: {str(e)}")
            return None
            
    def create_buffer(self, geometry: Union[Polygon, MultiPolygon], distance: float) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Erstellt einen Buffer um eine Geometrie.
        
        Args:
            geometry: Die Ausgangsgeometrie
            distance: Buffer-Distanz in Metern
            
        Returns:
            Optional[Union[Polygon, MultiPolygon]]: Die Buffer-Geometrie
        """
        try:
            if not self.validate_geometry(geometry):
                return None
                
            return geometry.buffer(distance)
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Buffer-Erstellung: {str(e)}")
            return None 
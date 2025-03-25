"""
WFS Geometrie-Prozessor für die Verarbeitung von Geometrien.
"""

from typing import Tuple, Optional, Dict, Any, List, Union
import geopandas as gpd
from shapely.geometry import box, Polygon, MultiPolygon
from shapely.ops import unary_union
import logging

logger = logging.getLogger(__name__)

class WFSGeometryProcessor:
    """Prozessor für WFS-Geometrieverarbeitung."""
    
    def __init__(self, srs_name: str = 'EPSG:31256'):
        """Initialisiert den Geometrie-Prozessor.
        
        Args:
            srs_name: Koordinatensystem (default: EPSG:31256)
        """
        self.logger = logging.getLogger(__name__)
        self.srs_name = srs_name
        
    def format_bbox(self, bounds: Tuple[float, float, float, float]) -> str:
        """Formatiert BBOX für WFS 1.1.0 Format.
        
        Args:
            bounds: Tuple (min_x, min_y, max_x, max_y)
            
        Returns:
            str: Formatierte BBOX
        """
        try:
            if len(bounds) != 4:
                raise ValueError("BBOX muss 4 Koordinaten enthalten")
                
            min_x, min_y, max_x, max_y = bounds
            # Formatiere Koordinaten für Vienna WFS (ganzzahlig)
            bbox = f"{int(min_x)},{int(min_y)},{int(max_x)},{int(max_y)},{self.srs_name}"
            return bbox
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der BBOX-Formatierung: {str(e)}")
            return None
            
    def create_bbox_from_polygon(self, polygon: Polygon) -> Optional[str]:
        """Erstellt eine BBOX aus einem Polygon.
        
        Args:
            polygon: Shapely Polygon
            
        Returns:
            Optional[str]: Formatierte BBOX oder None bei Fehler
        """
        try:
            bounds = polygon.bounds
            return self.format_bbox(bounds)
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der BBOX-Erstellung aus Polygon: {str(e)}")
            return None
            
    def create_bbox_from_gdf(self, gdf: gpd.GeoDataFrame) -> Optional[str]:
        """Erstellt eine BBOX aus einem GeoDataFrame.
        
        Args:
            gdf: GeoDataFrame mit Geometrien
            
        Returns:
            Optional[str]: Formatierte BBOX oder None bei Fehler
        """
        try:
            if gdf.empty:
                raise ValueError("GeoDataFrame ist leer")
                
            # Prüfe CRS
            if gdf.crs is None:
                self.logger.warning("⚠️ GeoDataFrame hat kein CRS")
            elif str(gdf.crs) != self.srs_name:
                self.logger.warning(f"⚠️ GeoDataFrame CRS ({gdf.crs}) unterscheidet sich von WFS CRS ({self.srs_name})")
                
            bounds = gdf.total_bounds
            return self.format_bbox(bounds)
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der BBOX-Erstellung aus GeoDataFrame: {str(e)}")
            return None
            
    def validate_geometry(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Validiert und bereinigt Geometrien.
        
        Args:
            gdf: GeoDataFrame mit Geometrien
            
        Returns:
            gpd.GeoDataFrame: Bereinigter GeoDataFrame
        """
        try:
            # Entferne ungültige Geometrien
            valid_mask = gdf.geometry.is_valid
            invalid_count = (~valid_mask).sum()
            
            if invalid_count > 0:
                self.logger.warning(f"⚠️ {invalid_count} ungültige Geometrien gefunden")
                gdf = gdf[valid_mask].copy()
                
            # Versuche ungültige Geometrien zu reparieren
            gdf.geometry = gdf.geometry.make_valid()
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrie-Validierung: {str(e)}")
            return gdf

class WFSGeometry:
    """Klasse für die Verarbeitung von WFS-Geometrien."""
    
    def __init__(self):
        """Initialisiert die WFS-Geometrie-Verarbeitung."""
        pass
        
    def validate_geometry(self, geometry: Union[Polygon, MultiPolygon]) -> bool:
        """
        Validiert eine Geometrie.
        
        Args:
            geometry: Die zu validierende Geometrie
            
        Returns:
            bool: True wenn die Geometrie valide ist
        """
        try:
            if geometry is None:
                return False
                
            return geometry.is_valid
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrie-Validierung: {str(e)}")
            return False
            
    def simplify_geometry(self, geometry: Union[Polygon, MultiPolygon], tolerance: float = 0.1) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Vereinfacht eine Geometrie.
        
        Args:
            geometry: Die zu vereinfachende Geometrie
            tolerance: Toleranz für die Vereinfachung
            
        Returns:
            Optional[Union[Polygon, MultiPolygon]]: Die vereinfachte Geometrie
        """
        try:
            if not self.validate_geometry(geometry):
                return None
                
            return geometry.simplify(tolerance, preserve_topology=True)
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrie-Vereinfachung: {str(e)}")
            return None
            
    def extract_footprint(self, geometry: Union[Polygon, MultiPolygon]) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Extrahiert den Grundriss aus einer Geometrie.
        
        Args:
            geometry: Die Ausgangsgeometrie
            
        Returns:
            Optional[Union[Polygon, MultiPolygon]]: Der extrahierte Grundriss
        """
        try:
            if not self.validate_geometry(geometry):
                return None
                
            # Bei MultiPolygon den größten Polygon nehmen
            if isinstance(geometry, MultiPolygon):
                return max(geometry.geoms, key=lambda x: x.area)
                
            return geometry
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Grundriss-Extraktion: {str(e)}")
            return None
            
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
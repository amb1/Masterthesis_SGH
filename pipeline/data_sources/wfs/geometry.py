"""
WFS Geometrie-Prozessor für die Verarbeitung von Geometrien.
"""

from typing import Tuple, Optional
import geopandas as gpd
from shapely.geometry import box, Polygon
import logging

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
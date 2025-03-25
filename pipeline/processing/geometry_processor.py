"""
Geometrie-Prozessor für räumliche Transformationen.

Dieser Prozessor implementiert geometrische Operationen und Transformationen.
"""

from typing import Dict, Any, List, Optional
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import logging

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class GeometryProcessor(BaseProcessor):
    """Prozessor für geometrische Operationen."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Geometrie-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        self.target_crs = config.get('crs', 'EPSG:31256')
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Geometrien.
        
        Args:
            data: Eingabedaten mit Geometrien
            
        Returns:
            Verarbeitete Daten
        """
        try:
            if not self.validate_data(data):
                return {}
                
            # Konvertiere zu GeoDataFrame wenn nötig
            if isinstance(data, dict) and 'geometry' in data:
                gdf = gpd.GeoDataFrame([data])
            elif isinstance(data, gpd.GeoDataFrame):
                gdf = data
            else:
                self.logger.error("❌ Ungültiges Eingabeformat")
                return {}
                
            # Transformiere CRS wenn nötig
            if gdf.crs != self.target_crs:
                gdf = self.transform_crs(gdf)
                
            # Validiere und bereinige Geometrien
            gdf = self.clean_geometries(gdf)
            
            # Berechne geometrische Attribute
            gdf = self.calculate_geometric_attributes(gdf)
            
            return gdf.to_dict('records')[0] if len(gdf) == 1 else gdf.to_dict('records')
            
        except Exception as e:
            self.handle_error(e, "geometry_processing")
            return {}
            
    def transform_crs(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Transformiert das Koordinatensystem.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            Transformierter GeoDataFrame
        """
        try:
            if gdf.crs is None:
                self.logger.warning("⚠️ Kein CRS definiert")
                return gdf
                
            if str(gdf.crs) != self.target_crs:
                self.logger.info(f"🔄 Transformiere von {gdf.crs} nach {self.target_crs}")
                return gdf.to_crs(self.target_crs)
                
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei CRS-Transformation: {str(e)}")
            return gdf
            
    def clean_geometries(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Bereinigt die Geometrien.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            Bereinigter GeoDataFrame
        """
        try:
            # Entferne ungültige Geometrien
            valid_mask = gdf.geometry.is_valid
            if not valid_mask.all():
                self.logger.warning(f"⚠️ {(~valid_mask).sum()} ungültige Geometrien gefunden")
                gdf = gdf[valid_mask].copy()
                
            # Konvertiere MultiPolygone zu Polygonen
            if any(gdf.geometry.type == 'MultiPolygon'):
                self.logger.info("🔄 Konvertiere MultiPolygone zu Polygonen")
                gdf = self.explode_multipolygons(gdf)
                
            # Vereinfache Geometrien wenn konfiguriert
            if self.config.get('simplify_tolerance'):
                gdf = self.simplify_geometries(gdf)
                
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Geometriebereinigung: {str(e)}")
            return gdf
            
    def calculate_geometric_attributes(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Berechnet geometrische Attribute.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            GeoDataFrame mit zusätzlichen Attributen
        """
        try:
            # Berechne Fläche
            gdf['area'] = gdf.geometry.area
            
            # Berechne Umfang
            gdf['perimeter'] = gdf.geometry.length
            
            # Berechne Zentroid
            centroids = gdf.geometry.centroid
            gdf['centroid_x'] = centroids.x
            gdf['centroid_y'] = centroids.y
            
            # Berechne Bounding Box
            bounds = gdf.geometry.bounds
            gdf['bbox_width'] = bounds.maxx - bounds.minx
            gdf['bbox_height'] = bounds.maxy - bounds.miny
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Attributberechnung: {str(e)}")
            return gdf
            
    def explode_multipolygons(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Zerlegt MultiPolygone in einzelne Polygone.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            GeoDataFrame mit einzelnen Polygonen
        """
        try:
            # Identifiziere MultiPolygone
            is_multi = gdf.geometry.type == 'MultiPolygon'
            
            if not is_multi.any():
                return gdf
                
            # Zerlege MultiPolygone
            singles = gdf[~is_multi].copy()
            multis = gdf[is_multi].copy()
            
            # Explodiere MultiPolygone
            exploded = multis.explode(index_parts=True)
            exploded = exploded.reset_index(drop=True)
            
            # Kombiniere zurück
            result = pd.concat([singles, exploded], ignore_index=True)
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Zerlegen von MultiPolygonen: {str(e)}")
            return gdf
            
    def simplify_geometries(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Vereinfacht die Geometrien.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            GeoDataFrame mit vereinfachten Geometrien
        """
        try:
            tolerance = float(self.config.get('simplify_tolerance', 0.1))
            
            self.logger.info(f"🔄 Vereinfache Geometrien (Toleranz: {tolerance})")
            gdf.geometry = gdf.geometry.simplify(tolerance, preserve_topology=True)
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Geometrievereinfachung: {str(e)}")
            return gdf 
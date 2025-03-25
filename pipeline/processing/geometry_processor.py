"""
Geometrie-Prozessor für räumliche Transformationen.

Dieser Prozessor implementiert geometrische Operationen und Transformationen.
"""

from typing import Dict, Any, List, Optional
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
import logging
import pandas as pd

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class GeometryProcessor(BaseProcessor):
    """Prozessor für Geometriedaten."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Geometrie-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        self.simplify_tolerance = config.get('simplify_tolerance', 0.1)
        self.crs = config.get('crs', 'EPSG:31256')  # MGI / Austria GK East als Standard
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet Geometriedaten.
        
        Args:
            data: Eingabedaten mit Geometrie
            
        Returns:
            Verarbeitete Geometriedaten
        """
        try:
            if not data or 'geometry' not in data:
                self.logger.warning("⚠️ Keine Geometrie in den Daten gefunden")
                return {}
                
            geometry = data['geometry']
            if not isinstance(geometry, (Polygon, MultiPolygon)):
                self.logger.warning("⚠️ Ungültiger Geometrietyp")
                return {}
                
            # Erstelle GeoDataFrame für CRS-Handling
            gdf = gpd.GeoDataFrame(geometry=[geometry], crs=self.crs)
            
            # Vereinfache Geometrie
            self.logger.info(f"🔄 Vereinfache Geometrien (Toleranz: {self.simplify_tolerance})")
            gdf.geometry = gdf.geometry.simplify(self.simplify_tolerance)
            
            # Extrahiere die vereinfachte Geometrie
            simplified = gdf.geometry.iloc[0]
            
            # Berechne Attribute
            area = gdf.geometry.area.iloc[0]
            orientation = self._calculate_orientation(simplified)
            footprint = self._calculate_footprint(simplified)
            
            return {
                'geometry': simplified,
                'area': area,
                'height': data.get('height', 0.0),
                'orientation': orientation,
                'footprint': footprint
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrieverarbeitung: {str(e)}")
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
                invalid_count = (~valid_mask).sum()
                self.logger.warning(f"⚠️ {invalid_count} ungültige Geometrien gefunden")
                
                # Versuche Reparatur
                repaired = gdf.copy()
                for idx in repaired[~valid_mask].index:
                    try:
                        # Versuche verschiedene Reparaturmethoden
                        geom = repaired.loc[idx, 'geometry']
                        if not geom.is_valid:
                            # Methode 1: Buffer mit 0
                            fixed = geom.buffer(0)
                            if fixed.is_valid and fixed.area > 0:
                                repaired.loc[idx, 'geometry'] = fixed
                                continue
                                
                            # Methode 2: Vereinfache
                            fixed = geom.simplify(self.simplify_tolerance)
                            if fixed.is_valid and fixed.area > 0:
                                repaired.loc[idx, 'geometry'] = fixed
                                continue
                                
                            # Methode 3: Konvexe Hülle
                            fixed = geom.convex_hull
                            if fixed.is_valid and fixed.area > 0:
                                repaired.loc[idx, 'geometry'] = fixed
                                continue
                                
                    except Exception as e:
                        self.logger.warning(f"Reparatur fehlgeschlagen für Geometrie {idx}: {str(e)}")
                        
                # Entferne verbleibende ungültige Geometrien
                gdf = repaired[repaired.geometry.is_valid].copy()
                
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
            
            # Validiere explodierte Geometrien
            valid_mask = exploded.geometry.is_valid & (exploded.geometry.area > 0)
            if not valid_mask.all():
                self.logger.warning(f"⚠️ {(~valid_mask).sum()} ungültige Geometrien nach Explosion")
                exploded = exploded[valid_mask]
                
            # Kombiniere zurück
            result = pd.concat([singles, exploded], ignore_index=True)
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Zerlegen von MultiPolygonen: {str(e)}")
            return gdf
            
    def simplify_geometries(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Vereinfacht die Geometrien mit adaptiver Toleranz.
        
        Args:
            gdf: Eingabe-GeoDataFrame
            
        Returns:
            GeoDataFrame mit vereinfachten Geometrien
        """
        try:
            # Kopiere DataFrame
            simplified = gdf.copy()
            
            # Vereinfache jede Geometrie
            for idx, row in simplified.iterrows():
                geom = row.geometry
                if not geom.is_valid or geom.area <= 0:
                    continue
                    
                # Versuche verschiedene Toleranzen
                for tolerance in [self.simplify_tolerance, self.simplify_tolerance * 2]:
                    try:
                        simple = geom.simplify(tolerance)
                        if simple.is_valid and simple.area > 0:
                            simplified.loc[idx, 'geometry'] = simple
                            break
                    except:
                        continue
                        
            return simplified
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Geometrievereinfachung: {str(e)}")
            return gdf 
"""Site Polygon Processor für die Erstellung und Verwaltung von Grundstückspolygonen."""

from typing import Dict, Any, Optional
import geopandas as gpd
from shapely.geometry import Polygon
import logging
from pathlib import Path
from ..processing.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class SitePolygonProcessor(BaseProcessor):
    """Processor für die Erstellung und Verwaltung von Site-Polygonen."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiere den SitePolygonProcessor.
        
        Args:
            config: Konfigurationsdaten aus global.yml
        """
        super().__init__(config)
        self.buffer_distance = config.get('processing', {}).get('site_polygon', {}).get('buffer_distance', 3)
        self.simplify_tolerance = config.get('processing', {}).get('site_polygon', {}).get('simplify_tolerance', 0.5)
    
    def create_site_polygon(self, buildings_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Erstelle ein Site-Polygon aus den Gebäudegrundrissen.
        
        Args:
            buildings_gdf: GeoDataFrame mit Gebäudegrundrissen
            
        Returns:
            GeoDataFrame mit dem Site-Polygon
        """
        if buildings_gdf.empty:
            raise ValueError("Keine Gebäude für Site-Polygon-Erstellung vorhanden")
            
        logger.info("📐 Erstelle äußere Hülle um alle Gebäude")
        
        # Vereinige alle Gebäudegrundrisse
        union_poly = buildings_gdf.geometry.unary_union
        
        # Erstelle Buffer
        logger.info(f"🔲 Erstelle Buffer mit Abstand {self.buffer_distance}m")
        buffered_poly = union_poly.buffer(self.buffer_distance)
        
        # Vereinfache das Polygon
        if self.simplify_tolerance > 0:
            buffered_poly = buffered_poly.simplify(self.simplify_tolerance)
            
        # Erstelle GeoDataFrame
        site_gdf = gpd.GeoDataFrame(
            {'Name': ['Site'],
             'geometry': [buffered_poly]},
            crs=buildings_gdf.crs
        )
        
        # Logging der Ergebnisse
        logger.info("✅ Standortpolygon erstellt:")
        logger.info(f"- Fläche: {buffered_poly.area:.2f} m²")
        logger.info(f"- Umfang: {buffered_poly.length:.2f} m")
        
        return site_gdf
        
    def export_site_polygon(self, site_gdf: gpd.GeoDataFrame, output_path: str) -> None:
        """Exportiere das Site-Polygon als Shapefile.
        
        Args:
            site_gdf: GeoDataFrame mit dem Site-Polygon
            output_path: Pfad für die Ausgabedatei
        """
        logger.info(f"💾 Speichere Site-Polygon nach: {output_path}")
        site_gdf.to_file(output_path, driver=self.config.get('processing', {}).get('file_formats', {}).get('shp_driver', 'ESRI Shapefile'))
        logger.info("✅ Site-Polygon erfolgreich gespeichert")
        
    def process(self, buildings_path: str = None) -> None:
        """Hauptverarbeitungsmethode für die Site-Polygon-Erstellung.
        
        Args:
            buildings_path: Optional. Pfad zur zone.shp. Falls None, wird der Pfad aus der Konfiguration verwendet.
        """
        try:
            logger.info("🔄 Starte Site-Polygon Erstellung...")
            
            # Bestimme den Pfad zur zone.shp
            if buildings_path is None:
                paths = self.config.get('paths', {})
                buildings_path = Path(paths.get('outputs', {}).get('buildings', 'outputs/buildings'))
            else:
                buildings_path = Path(buildings_path)
                
            zone_path = buildings_path / 'zone.shp'
            if not zone_path.exists():
                raise FileNotFoundError(f"❌ zone.shp nicht gefunden in {zone_path}")
            
            # Lade Gebäudedaten
            logger.info(f"📂 Lade Gebäudedaten aus: {zone_path}")
            buildings_gdf = gpd.read_file(zone_path)
            
            # Erstelle und speichere Site-Polygon
            site_gdf = self.create_site_polygon(buildings_gdf)
            site_path = buildings_path / 'site.shp'
            self.export_site_polygon(site_gdf, site_path)
            
            logger.info("✅ Site-Polygon Erstellung erfolgreich abgeschlossen!")
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Site-Polygon Erstellung: {str(e)}")
            raise 
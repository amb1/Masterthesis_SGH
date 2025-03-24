"""Utilities für die Site-Polygon-Verarbeitung."""

import geopandas as gpd
from shapely.geometry import Polygon
import logging

logger = logging.getLogger(__name__)

def create_site_polygon(buildings_gdf: gpd.GeoDataFrame, buffer_distance: float = 3) -> gpd.GeoDataFrame:
    """Erstelle ein Site-Polygon aus den Gebäudegrundrissen.
    
    Args:
        buildings_gdf: GeoDataFrame mit Gebäudegrundrissen
        buffer_distance: Abstand in Metern für den Buffer um die Gebäude
        
    Returns:
        GeoDataFrame mit dem Site-Polygon
    """
    if buildings_gdf.empty:
        raise ValueError("Keine Gebäude für Site-Polygon-Erstellung vorhanden")
        
    logger.info("📐 Erstelle äußere Hülle um alle Gebäude")
    
    # Vereinige alle Gebäudegrundrisse
    union_poly = buildings_gdf.geometry.unary_union
    
    # Erstelle Buffer
    logger.info(f"🔲 Erstelle Buffer mit Abstand {buffer_distance}m")
    buffered_poly = union_poly.buffer(buffer_distance)
    
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

def save_site_polygon(site_gdf: gpd.GeoDataFrame, output_path: str, driver: str = 'ESRI Shapefile') -> None:
    """Exportiere das Site-Polygon als Shapefile.
    
    Args:
        site_gdf: GeoDataFrame mit dem Site-Polygon
        output_path: Pfad für die Ausgabedatei
        driver: GIS-Treiber für die Ausgabe
    """
    logger.info(f"💾 Speichere Site-Polygon nach: {output_path}")
    site_gdf.to_file(output_path, driver=driver)
    logger.info("✅ Site-Polygon erfolgreich gespeichert") 
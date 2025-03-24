"""Legacy-Wrapper für die Site-Polygon-Erstellung."""

import logging
from pathlib import Path
import sys
from typing import Optional
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from core.config_manager import load_config

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

logger = logging.getLogger(__name__)

def create_site_polygon(buildings_gdf: gpd.GeoDataFrame, buffer_distance: float = 3.0) -> Optional[gpd.GeoDataFrame]:
    """Erstellt ein Site-Polygon aus den Gebäude-Geometrien.
    
    Args:
        buildings_gdf: GeoDataFrame mit Gebäude-Geometrien
        buffer_distance: Buffer-Distanz in Metern (Standard: 3.0)
        
    Returns:
        GeoDataFrame mit dem Site-Polygon oder None bei Fehler
    """
    try:
        logger.info("🔄 Erstelle Site-Polygon aus Gebäuden...")
        
        if buildings_gdf.empty:
            logger.warning("⚠️ Keine Gebäude-Geometrien vorhanden")
            return None
            
        # Validiere Geometrien
        valid_geometries = []
        for geom in buildings_gdf.geometry:
            if isinstance(geom, (Polygon, MultiPolygon)) and geom.is_valid:
                valid_geometries.append(geom)
            else:
                logger.warning(f"⚠️ Ungültige Geometrie gefunden: {type(geom)}")
                
        if not valid_geometries:
            logger.error("❌ Keine gültigen Geometrien für Site-Polygon")
            return None
            
        # Erstelle Site-Polygon
        combined = unary_union(valid_geometries)
        buffered = combined.buffer(buffer_distance)
        
        # Erstelle GeoDataFrame
        site_gdf = gpd.GeoDataFrame(geometry=[buffered], crs=buildings_gdf.crs)
        
        logger.info(f"✅ Site-Polygon erstellt (Fläche: {buffered.area:.1f}m²)")
        return site_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Site-Polygons: {str(e)}")
        return None

def main():
    """Hauptfunktion für die Site-Polygon-Erstellung als Standalone-Skript."""
    try:
        logger.info("🔄 Starte Site-Polygon Erstellung...")
        
        # Lade Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        global_config_path = root_dir / 'config' / 'global.yml'
        logger.info(f"📂 Lade globale Konfiguration: {global_config_path}")
        
        global_config = load_config(global_config_path)
        if not global_config:
            raise ValueError("❌ Keine gültige Konfiguration gefunden")
            
        # Importiere SitePolygonProcessor erst hier
        from ..processing.site_polygon_processor import SitePolygonProcessor
        
        # Erstelle und führe den Processor aus
        processor = SitePolygonProcessor(global_config)
        processor.process()
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Site-Polygon Erstellung: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main() 
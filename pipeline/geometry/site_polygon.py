import geopandas as gpd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import numpy as np
from pathlib import Path
import yaml
import sys
import logging
from core.config_manager import load_config

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

logger = logging.getLogger(__name__)

def load_project_config():
    """Lädt die Projekt-Konfiguration"""
    try:
        # Lade zuerst die globale Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        global_config_path = root_dir / 'config' / 'global.yml'
        logger.info(f"📂 Lade globale Konfiguration: {global_config_path}")

        global_config = load_config(global_config_path)
        if not global_config:
            logger.error("❌ Globale Konfiguration konnte nicht geladen werden")
            return None

        return global_config

    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        return None

def create_site_polygon(buildings_gdf: gpd.GeoDataFrame, buffer_distance: float = 3) -> gpd.GeoDataFrame:
    """Erstellt ein einzelnes Polygon, das alle Gebäude umschließt"""
    if 'geometry' not in buildings_gdf.columns or buildings_gdf.geometry.isnull().all():
        print("⚠️ Warnung: buildings_gdf enthält keine gültigen Geometrien")
        site_polygon = box(*buildings_gdf.total_bounds)
    else:
        print("📐 Erstelle äußere Hülle um alle Gebäude")
        all_buildings = unary_union(buildings_gdf.geometry)
        
        print(f"🔲 Erstelle Buffer mit Abstand {buffer_distance}m")
        site_polygon = all_buildings.convex_hull.buffer(buffer_distance)
        site_polygon = site_polygon.simplify(tolerance=0.5)

    site_gdf = gpd.GeoDataFrame(
        {'Name': ['Site'],
         'geometry': [site_polygon]},
        crs=buildings_gdf.crs
    )

    print("✅ Standortpolygon erstellt:")
    print(f"- Fläche: {site_polygon.area:.2f} m²")
    print(f"- Umfang: {site_polygon.length:.2f} m")

    return site_gdf

def save_site_polygon(site_gdf, output_path):
    """Speichert das Site-Polygon als Shapefile"""
    print(f"Speichere Site-Polygon nach: {output_path}")
    site_gdf.to_file(output_path, driver='ESRI Shapefile')
    print("Site-Polygon erfolgreich gespeichert")

def main():
    try:
        logger.info("🔄 Starte Site-Polygon Erstellung...")
        
        # Lade Konfiguration
        global_config = load_project_config()
        if not global_config:
            raise ValueError("❌ Keine gültige Konfiguration gefunden")
        
        # Hole Pfade aus der Konfiguration
        paths = global_config.get('paths', {})
        buildings_path = Path(paths.get('outputs', {}).get('buildings', 'outputs/buildings'))
        
        # Hole Verarbeitungsparameter
        processing = global_config.get('processing', {}).get('site_polygon', {})
        buffer_distance = processing.get('buffer_distance', 3)
        simplify_tolerance = processing.get('simplify_tolerance', 0.5)
        
        # Überprüfe ob zone.shp existiert
        zone_path = buildings_path / 'zone.shp'
        if not zone_path.exists():
            raise FileNotFoundError(f"❌ zone.shp nicht gefunden in {zone_path}")
        
        # Lade Gebäudedaten
        logger.info(f"📂 Lade Gebäudedaten aus: {zone_path}")
        buildings_gdf = gpd.read_file(zone_path)
        
        # Erstelle Site-Polygon
        logger.info(f"📐 Erstelle Site-Polygon mit Buffer {buffer_distance}m")
        site_gdf = create_site_polygon(
            buildings_gdf,
            buffer_distance=buffer_distance
        )
        
        # Speichere Site-Polygon
        site_path = buildings_path / 'site.shp'
        logger.info(f"💾 Speichere Site-Polygon nach: {site_path}")
        save_site_polygon(site_gdf, site_path)
        
        logger.info("✅ Site-Polygon Erstellung erfolgreich abgeschlossen!")
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Site-Polygon Erstellung: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    main() 
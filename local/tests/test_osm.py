import os
import sys
from pathlib import Path
import geopandas as gpd
import yaml
import logging
from shapely.geometry import box

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(local_dir))

from utils.data_sources.fetch_osm_buildings import fetch_osm_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_processing.create_site_polygon import create_site_polygon

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_osm_processing():
    """Testet die OSM-Datenverarbeitung mit Beispielsdaten"""
    try:
        # Lade Konfigurationen
        configs = {
            'osm': load_config(local_dir / "cfg" / "data_sources" / "osm_config.yml"),
            'project': load_config(local_dir / "cfg" / "project_config.yml")
        }

        # Erstelle Testverzeichnis
        test_dir = local_dir / "tests" / "output"
        test_dir.mkdir(exist_ok=True)

        # Erstelle Testgebiet (1. Bezirk Wien)
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326")
        
        # Erstelle Site-Polygon
        site_gdf = create_site_polygon(test_gdf, buffer_distance=3.0)

        # Teste Gebäudeabfrage
        logger.info("\n🔄 Teste OSM-Gebäudeabfrage...")
        buildings_gdf = fetch_osm_buildings(
            site_polygon=site_gdf,
            config=configs['project']
        )

        if buildings_gdf is not None and not buildings_gdf.empty:
            logger.info(f"✅ {len(buildings_gdf)} OSM-Gebäude gefunden")
            logger.info(f"Spalten: {', '.join(buildings_gdf.columns)}")
            buildings_gdf.to_file(test_dir / "osm_buildings.shp")
        else:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden")

        # Teste Straßenabfrage
        logger.info("\n🔄 Teste OSM-Straßenabfrage...")
        streets_gdf = fetch_osm_streets(
            site_polygon=site_gdf,
            config={
                'osm': configs['osm'],
                'geometry': configs['project']['geometry']
            }
        )

        if streets_gdf is not None and not streets_gdf.empty:
            logger.info(f"✅ {len(streets_gdf)} OSM-Straßen gefunden")
            logger.info(f"Spalten: {', '.join(streets_gdf.columns)}")
            streets_gdf.to_file(test_dir / "osm_streets.shp")
        else:
            logger.warning("⚠️ Keine OSM-Straßen gefunden")

    except Exception as e:
        logger.error(f"❌ Fehler bei der OSM-Verarbeitung: {str(e)}", exc_info=True)

def load_config(config_path):
    """Lädt eine YAML-Konfigurationsdatei"""
    try:
        with open(config_path, 'r', encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
        return None

if __name__ == "__main__":
    test_osm_processing() 
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

from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings
from utils.data_processing.create_site_polygon import create_site_polygon

# Konfiguriere Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_citygml():
    """Erstellt eine Test-CityGML-Datei mit Beispielgebäuden"""
    try:
        # Erstelle Verzeichnis, falls nicht vorhanden
        citygml_dir = local_dir / "data" / "citygml"
        citygml_dir.mkdir(parents=True, exist_ok=True)
        
        # Erstelle ein einfaches Testgebäude
        test_building = box(16.35, 48.20, 16.36, 48.21)
        test_gdf = gpd.GeoDataFrame(geometry=[test_building], crs="EPSG:4326")
        
        # Speichere als GML
        test_citygml = citygml_dir / "test.gml"
        test_gdf.to_file(test_citygml, driver="GML")
        logger.info(f"✅ Test-CityGML-Datei erstellt: {test_citygml}")
        return test_citygml
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der Test-CityGML-Datei: {str(e)}")
        return None

def test_citygml_processing():
    """Testet die CityGML-Verarbeitung mit Beispielsdaten"""
    try:
        # Lade Konfigurationen
        configs = {
            'citygml': load_config(local_dir / "cfg" / "data_sources" / "vienna_citygml_normalized.yml"),
            'project': load_config(local_dir / "cfg" / "project_config.yml"),
            'wfs': load_config(local_dir / "cfg" / "wfs" / "wfs_config.yml")
        }

        # Füge WFS-Konfiguration zur CityGML-Konfiguration hinzu
        configs['citygml']['vienna_wfs'] = configs['wfs']['vienna_wfs']

        # Erstelle Testverzeichnis
        test_dir = local_dir / "tests" / "output"
        test_dir.mkdir(exist_ok=True)

        # Überprüfe oder erstelle Test-CityGML-Datei
        test_citygml = local_dir / "data" / "citygml" / "test.gml"
        if not test_citygml.exists():
            logger.info("Test-CityGML-Datei nicht gefunden, erstelle neue...")
            test_citygml = create_test_citygml()
            if not test_citygml or not test_citygml.exists():
                logger.error("❌ Konnte keine Test-CityGML-Datei erstellen")
                return

        # Erstelle Site-Polygon für das Testgebiet
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326")
        site_gdf = create_site_polygon(test_gdf, buffer_distance=3.0)

        # Verarbeite CityGML
        logger.info("\n🔄 Verarbeite CityGML-Daten...")
        buildings_gdf = fetch_citygml_buildings(
            citygml_path=test_citygml,
            config=configs['citygml'],
            cea_config=configs['project'],
            site_polygon=site_gdf
        )

        if buildings_gdf is not None and not buildings_gdf.empty:
            logger.info(f"✅ {len(buildings_gdf)} Gebäude verarbeitet")
            logger.info(f"Spalten: {', '.join(buildings_gdf.columns)}")
            
            # Speichere verarbeitete Gebäude
            buildings_gdf.to_file(test_dir / "processed_buildings.shp")
            logger.info("✅ Verarbeitete Gebäude gespeichert")
        else:
            logger.error("❌ Keine Gebäude in der CityGML-Datei gefunden")

    except Exception as e:
        logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}", exc_info=True)

def load_config(config_path):
    """Lädt eine YAML-Konfigurationsdatei"""
    try:
        with open(config_path, 'r', encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
        return None

if __name__ == "__main__":
    test_citygml_processing() 
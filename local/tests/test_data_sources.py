import os
import sys
import logging
from pathlib import Path
import yaml
import geopandas as gpd
from shapely.geometry import box
import time

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(local_dir))

from utils.data_sources.fetch_wfs_data import ViennaWFS
from utils.data_sources.fetch_citygml import CityGMLFetcher
from utils.data_sources.fetch_osm import OSMFetcher
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings

# Logger einrichten
logger = logging.getLogger("DataSourcesTest")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def load_config():
    """Lädt die Projekt-Konfiguration"""
    try:
        config_path = local_dir / "cfg" / "project_config.yml"
        logger.info(f"📂 Lade Konfiguration: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        return config
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}", exc_info=True)
        return None

def test_wfs_data():
    """Testet den WFS-Datenabruf"""
    try:
        logger.info("\n🔍 Teste WFS-Datenabruf...")
        
        # Lade WFS-Konfiguration
        wfs_config_path = local_dir / "cfg" / "wfs" / "wfs_config.yml"
        with open(wfs_config_path, 'r', encoding='utf-8') as f:
            wfs_config = yaml.safe_load(f)
        
        # Erstelle Testgebiet (Wien)
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")
        
        # Initialisiere WFS
        wfs = ViennaWFS(wfs_config)
        
        # Teste verschiedene Layer
        layers = [
            "ogdwien:GEBAEUDEINFOOGD",
            "ogdwien:FMZKBKMOGD"
        ]
        
        for layer in layers:
            start_time = time.time()
            data = wfs.fetch_layer(layer, test_gdf.total_bounds)
            duration = time.time() - start_time
            
            if data is not None:
                logger.info(f"✅ Layer {layer}: {len(data)} Features in {duration:.2f}s geladen")
            else:
                logger.warning(f"⚠️ Keine Daten für Layer {layer}")
                
    except Exception as e:
        logger.error(f"❌ Fehler beim WFS-Test: {str(e)}", exc_info=True)

def test_citygml_data():
    """Testet den CityGML-Datenabruf"""
    try:
        logger.info("\n🔍 Teste CityGML-Datenabruf...")
        
        # Lade Konfiguration
        config = load_config()
        if not config:
            raise ValueError("Keine gültige Konfiguration gefunden")
            
        # Erstelle Testgebiet
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")
        
        # Teste beide CityGML-Implementierungen
        # 1. CityGMLFetcher
        fetcher = CityGMLFetcher(config)
        start_time = time.time()
        data = fetcher.fetch_data(test_gdf)
        duration = time.time() - start_time
        
        if data is not None:
            logger.info(f"✅ CityGMLFetcher: {len(data)} Features in {duration:.2f}s geladen")
        else:
            logger.warning("⚠️ Keine Daten mit CityGMLFetcher")
            
        # 2. fetch_citygml_buildings
        citygml_path = Path(config['paths']['inputs']['citygml'])
        if citygml_path.exists():
            start_time = time.time()
            buildings = fetch_citygml_buildings(
                citygml_path=citygml_path,
                config=config.get('citygml', {}),
                cea_config=config
            )
            duration = time.time() - start_time
            
            if buildings is not None and not buildings.empty:
                logger.info(f"✅ fetch_citygml_buildings: {len(buildings)} Gebäude in {duration:.2f}s geladen")
            else:
                logger.warning("⚠️ Keine Gebäude mit fetch_citygml_buildings")
        else:
            logger.warning(f"⚠️ CityGML-Datei nicht gefunden: {citygml_path}")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim CityGML-Test: {str(e)}", exc_info=True)

def test_osm_data():
    """Testet den OSM-Datenabruf"""
    try:
        logger.info("\n🔍 Teste OSM-Datenabruf...")
        
        # Lade Konfiguration
        config = load_config()
        if not config:
            raise ValueError("Keine gültige Konfiguration gefunden")
            
        # Erstelle Testgebiet
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")
        
        # Initialisiere OSM-Fetcher
        fetcher = OSMFetcher(config)
        
        # Teste Gebäudeabruf
        start_time = time.time()
        data = fetcher.fetch_data(test_gdf)
        duration = time.time() - start_time
        
        if data is not None:
            logger.info(f"✅ OSM: {len(data)} Features in {duration:.2f}s geladen")
        else:
            logger.warning("⚠️ Keine OSM-Daten gefunden")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Test: {str(e)}", exc_info=True)

def main():
    """Hauptfunktion zum Testen aller Datenquellen"""
    try:
        logger.info("🚀 Starte Tests der Datenquellen...")
        
        # Teste WFS
        test_wfs_data()
        
        # Teste CityGML
        test_citygml_data()
        
        # Teste OSM
        test_osm_data()
        
        logger.info("✅ Alle Tests abgeschlossen!")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Ausführen der Tests: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
import os
import sys
from pathlib import Path
import geopandas as gpd
import yaml
import logging
from shapely.geometry import box
import time

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(local_dir))

from utils.data_sources.fetch_wfs_data import ViennaWFS
from utils.data_processing.create_site_polygon import create_site_polygon

# Logger einrichten
logger = logging.getLogger("WFS-Test")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def test_wfs_connection():
    """Testet die WFS-Verbindung und lädt Beispiel-Daten."""
    try:
        logger.info("🔄 Starte WFS-Verbindungstest...")
        
        # Lade Konfigurationen
        config_path = Path(__file__).resolve().parent.parent / "cfg" / "project_config.yml"
        with open(config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)
            
        wfs_config_path = Path(__file__).resolve().parent.parent / "cfg" / "wfs" / "wfs_config.yml"
        with open(wfs_config_path, 'r', encoding="utf-8") as f:
            wfs_config = yaml.safe_load(f)
            
        # Kombiniere Konfigurationen
        config['vienna_wfs'] = wfs_config['vienna_wfs']
        
        # Erstelle Test-Verzeichnis
        output_dir = Path(__file__).resolve().parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Definiere Test-Bereich (1. Bezirk Wien)
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326")
        
        # Konvertiere in das richtige CRS
        test_gdf = test_gdf.to_crs("EPSG:31256")
        logger.info(f"📍 Test-Bereich definiert: {test_gdf.total_bounds}")
        
        # Initialisiere WFS-Service
        wfs = ViennaWFS(config)
        
        # Teste verschiedene Layer
        layers = [
            "ogdwien:GEBAEUDEINFOOGD"
        ]
        
        for layer in layers:
            try:
                start_time = time.time()
                logger.info(f"🔄 Lade Layer: {layer}")
                
                data = wfs.fetch_layer(layer, test_gdf.total_bounds)
                
                if data is not None:
                    logger.info(f"✅ {len(data)} Features geladen")
                    logger.info(f"⏱️ Ladezeit: {time.time() - start_time:.2f} Sekunden")
                    
                    # Speichere als Shapefile
                    output_file = output_dir / f"{layer.replace(':', '_')}.shp"
                    data.to_file(output_file)
                    logger.info(f"💾 Daten gespeichert in: {output_file}")
                else:
                    logger.warning(f"⚠️ Keine Daten für Layer: {layer}")
                    
            except Exception as e:
                logger.error(f"❌ Fehler bei Layer {layer}: {str(e)}", exc_info=True)
                
    except Exception as e:
        logger.error(f"❌ Fehler im WFS-Test: {str(e)}", exc_info=True)

def load_config(config_path):
    """Lädt eine YAML-Konfigurationsdatei"""
    try:
        with open(config_path, 'r', encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
        return None

if __name__ == "__main__":
    test_wfs_connection() 
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
from utils.data_sources.fetch_citygml import CityGMLFetcher
from utils.data_sources.fetch_osm import OSMFetcher
from utils.data_processing.create_site_polygon import create_site_polygon
from utils.data_processing.validate_data import validate_data

# Logger einrichten
logger = logging.getLogger("Data-Integration-Test")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def load_config(config_path):
    """Lädt eine YAML-Konfigurationsdatei"""
    try:
        with open(config_path, 'r', encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
        return None

def test_data_integration():
    """Testet die Integration aller Datenquellen"""
    try:
        logger.info("🔄 Starte Datenintegrations-Test...")
        
        # Lade Konfigurationen
        config_path = Path(__file__).resolve().parent.parent / "cfg" / "project_config.yml"
        config = load_config(config_path)
        
        integration_config_path = Path(__file__).resolve().parent.parent / "cfg" / "data_integration_config.yml"
        integration_config = load_config(integration_config_path)
        
        if not config or not integration_config:
            logger.error("❌ Konfiguration konnte nicht geladen werden")
            return
            
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
        
        # Initialisiere Datenquellen
        wfs = ViennaWFS(config)
        citygml = CityGMLFetcher(config)
        osm = OSMFetcher(config)
        
        # Teste WFS-Daten
        wfs_layers = [
            "ogdwien:GEBAEUDEINFOOGD",
            "ogdwien:ENERGIERAUMPLANOGD",
            "ogdwien:PVPOTENZIALEOGD"
        ]
        
        for layer in wfs_layers:
            try:
                start_time = time.time()
                logger.info(f"🔄 Lade WFS Layer: {layer}")
                
                data = wfs.fetch_layer(layer, test_gdf.total_bounds)
                
                if data is not None:
                    # Validiere Daten
                    if validate_data(data, integration_config, "buildings"):
                        logger.info(f"✅ {len(data)} Features geladen und validiert")
                        logger.info(f"⏱️ Ladezeit: {time.time() - start_time:.2f} Sekunden")
                        
                        # Speichere in verschiedenen Formaten
                        for output_format in integration_config['integration']['output_formats']:
                            output_file = output_dir / f"wfs_{layer.replace(':', '_')}.{output_format['format']}"
                            data.to_file(output_file, driver=output_format['driver'])
                            logger.info(f"💾 Daten gespeichert in: {output_file}")
                    else:
                        logger.error(f"❌ Validierung fehlgeschlagen für Layer: {layer}")
                else:
                    logger.warning(f"⚠️ Keine Daten für Layer: {layer}")
                    
            except Exception as e:
                logger.error(f"❌ Fehler bei Layer {layer}: {str(e)}", exc_info=True)
        
        # Teste CityGML-Daten
        try:
            start_time = time.time()
            logger.info("🔄 Lade CityGML Daten...")
            
            citygml_data = citygml.fetch_data(test_gdf)
            
            if citygml_data is not None:
                # Validiere Daten
                if validate_data(citygml_data, integration_config, "buildings"):
                    logger.info(f"✅ {len(citygml_data)} Features geladen und validiert")
                    logger.info(f"⏱️ Ladezeit: {time.time() - start_time:.2f} Sekunden")
                    
                    # Speichere in verschiedenen Formaten
                    for output_format in integration_config['integration']['output_formats']:
                        output_file = output_dir / f"citygml_data.{output_format['format']}"
                        citygml_data.to_file(output_file, driver=output_format['driver'])
                        logger.info(f"💾 Daten gespeichert in: {output_file}")
                else:
                    logger.error("❌ Validierung der CityGML-Daten fehlgeschlagen")
            else:
                logger.warning("⚠️ Keine CityGML-Daten erhalten")
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der CityGML-Daten: {str(e)}", exc_info=True)
        
        # Teste OSM-Daten
        try:
            start_time = time.time()
            logger.info("🔄 Lade OSM Daten...")
            
            osm_data = osm.fetch_data(test_gdf)
            
            if osm_data is not None:
                # Validiere Daten
                if validate_data(osm_data, integration_config, "buildings"):
                    logger.info(f"✅ {len(osm_data)} Features geladen und validiert")
                    logger.info(f"⏱️ Ladezeit: {time.time() - start_time:.2f} Sekunden")
                    
                    # Speichere in verschiedenen Formaten
                    for output_format in integration_config['integration']['output_formats']:
                        output_file = output_dir / f"osm_data.{output_format['format']}"
                        osm_data.to_file(output_file, driver=output_format['driver'])
                        logger.info(f"💾 Daten gespeichert in: {output_file}")
                else:
                    logger.error("❌ Validierung der OSM-Daten fehlgeschlagen")
            else:
                logger.warning("⚠️ Keine OSM-Daten erhalten")
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der OSM-Daten: {str(e)}", exc_info=True)
            
    except Exception as e:
        logger.error(f"❌ Fehler im Datenintegrations-Test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    test_data_integration() 
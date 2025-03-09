import os
import sys
import logging
from pathlib import Path
import yaml
import geopandas as gpd
import time

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(local_dir))

from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings

# Logger einrichten
logger = logging.getLogger("CityGMLBuildingsTest")
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

def main():
    """Hauptfunktion zum Testen der CityGML-Verarbeitung"""
    try:
        logger.info("🚀 Starte CityGML-Gebäude Test...")
        
        # Lade Konfiguration
        config = load_config()
        if not config:
            raise ValueError("Keine gültige Konfiguration gefunden")
            
        # Definiere Pfade
        citygml_path = local_dir / "data" / "citygml" / "099082.gml"
        output_dir = local_dir / "data" / "outputs" / "buildings"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        if not citygml_path.exists():
            raise FileNotFoundError(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            
        logger.info(f"📂 Verarbeite CityGML-Datei: {citygml_path}")
        
        # Erstelle CityGML-spezifische Konfiguration
        citygml_config = {
            'vienna_wfs': config['vienna_wfs'],
            'citygml': config['citygml'],
            'paths': config['paths']
        }
        
        # Verarbeite CityGML-Datei
        start_time = time.time()
        buildings = fetch_citygml_buildings(
            citygml_path=citygml_path,
            config=citygml_config,
            cea_config=config
        )
        duration = time.time() - start_time
        
        if buildings is not None and not buildings.empty:
            logger.info(f"✅ {len(buildings)} Gebäude in {duration:.2f}s geladen")
            
            # Speichere Ergebnisse in verschiedenen Formaten
            # 1. GeoJSON
            geojson_path = output_dir / "buildings.geojson"
            buildings.to_file(geojson_path, driver="GeoJSON")
            logger.info(f"💾 GeoJSON gespeichert: {geojson_path}")
            
            # 2. Shapefile
            shp_path = output_dir / "buildings.shp"
            buildings.to_file(shp_path, driver="ESRI Shapefile")
            logger.info(f"💾 Shapefile gespeichert: {shp_path}")
            
            # 3. GPKG
            gpkg_path = output_dir / "buildings.gpkg"
            buildings.to_file(gpkg_path, driver="GPKG")
            logger.info(f"💾 GeoPackage gespeichert: {gpkg_path}")
            
            # Zeige Gebäudestatistiken
            logger.info("\n📊 Gebäudestatistiken:")
            logger.info(f"- Gesamtanzahl Gebäude: {len(buildings)}")
            if 'height_ag' in buildings.columns:
                logger.info(f"- Durchschnittliche Höhe: {buildings['height_ag'].mean():.2f}m")
            if 'floors_ag' in buildings.columns:
                logger.info(f"- Durchschnittliche Stockwerke: {buildings['floors_ag'].mean():.2f}")
            if 'construction_year' in buildings.columns:
                logger.info(f"- Baujahre von {buildings['construction_year'].min()} bis {buildings['construction_year'].max()}")
            
        else:
            logger.warning("⚠️ Keine Gebäude gefunden")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim CityGML-Test: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main() 
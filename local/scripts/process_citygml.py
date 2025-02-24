import sys
import yaml
import logging
from pathlib import Path
from datetime import datetime
import geopandas as gpd

# Füge Projekt-Root zum Python-Path hinzu
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Importiere Module
from utils.setup_project_paths import setup_project_paths
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings, CityGMLBuildingProcessor
from utils.data_sources.fetch_wfs_data import ViennaWFS
from utils.data_sources.fetch_osm_buildings import fetch_osm_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_processing.create_site_polygon import create_site_polygon
from utils.data_processing.cea_building_processor import CEABuildingProcessor

def setup_logger():
    """Initialisiert einen Logger"""
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'citygml_processing_{timestamp}.log'

    logger = logging.getLogger('CityGMLProcessor')
    logger.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def load_config(config_path: Path, logger):
    """Lädt YAML-Konfigurationsdateien"""
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)

        logger.info(f"✅ Konfiguration geladen: {config_path.name}")
        return config

    except Exception as e:
        logger.error(f"❌ Fehler beim Laden von {config_path}: {str(e)}")
        return None

def process_citygml(citygml_path: Path, project_name: str, scenario_name: str, logger):
    """Verarbeitet CityGML Daten und erstellt vollständiges CEA Projekt"""
    try:
        logger.info("\n=== 🏗 CityGML Verarbeitung gestartet ===")

        # 1. Lade Konfigurationen
        citygml_config = load_config(project_root / "cfg" / "data_sources" / "vienna_citygml_normalized.yml", logger)
        cea_config = load_config(project_root / "cfg" / "cea" / "cea_fields.yml", logger)
        project_config = load_config(project_root / "cfg" / "project_config.yml", logger)
        osm_config = load_config(project_root / "cfg" / "data_sources" / "osm_config.yml", logger)

        # 2. Initialisiere CEA Processor & Projektstruktur
        cea_processor = CEABuildingProcessor(citygml_config, cea_config)
        project_paths = cea_processor.setup_project_structure(project_name, scenario_name, project_root)

        # 3. Verarbeite CityGML zu GeoDataFrame
        buildings_gdf = fetch_citygml_buildings(citygml_path, citygml_config, cea_config)
        logger.info(f"✅ CityGML verarbeitet: {len(buildings_gdf)} Gebäude")

        if 'geometry' not in buildings_gdf.columns:
            logger.error("❌ FEHLER: buildings_gdf hat KEINE 'geometry'-Spalte nach CityGML-Verarbeitung!")
            logger.info(buildings_gdf.head())  # Debug-Ausgabe
            return None
                
        # 4. WFS Anreicherung
        wfs = ViennaWFS()
        buildings_gdf = wfs.enrich_buildings(buildings_gdf)

        if 'geometry' not in buildings_gdf.columns:
            logger.error("❌ FEHLER: buildings_gdf hat KEINE 'geometry'-Spalte mehr nach WFS-Anreicherung!")
            logger.info(buildings_gdf.head())  # Debug-Ausgabe
            return None

        logger.info("✅ WFS Anreicherung abgeschlossen")

        # 5. Erstelle Site Polygon
        site_polygon = create_site_polygon(buildings_gdf, buffer_distance=project_config['geometry']['site_buffer_distance'])

        # 🛑 TEST: Enthält site_polygon eine Geometrie?
        if site_polygon.empty or 'geometry' not in site_polygon.columns:
            logger.error("❌ FEHLER: site_polygon konnte nicht erstellt werden!")
            logger.info(site_polygon)
            return None

        # 6. Hole OSM Gebäude
        osm_buildings = fetch_osm_buildings(
            site_polygon,
            distance=project_config['geometry']['surrounding_buildings_distance']
        )
        logger.info(f"✅ OSM Gebäude geladen: {len(osm_buildings)}")

        # 7. Hole OSM Straßen
        street_types = osm_config.get('streets', [])
        logger.info(f"📍 Hole OSM-Straßen für Kategorien: {street_types}")
        osm_streets = fetch_osm_streets(site_polygon, street_types=street_types)
        logger.info(f"✅ OSM Straßen geladen: {len(osm_streets)}")

        # 8. Speichere Ergebnisse
        cea_processor.save_zone_shapefile(buildings_gdf, project_paths)
        cea_processor.save_typology_shapefile(buildings_gdf, project_paths)

        osm_buildings.to_file(project_paths['geometry'] / "surroundings.shp", driver="ESRI Shapefile")
        site_polygon.to_file(project_paths['geometry'] / "site.shp", driver="ESRI Shapefile")
        osm_streets.to_file(project_paths['networks'] / "streets.shp", driver="ESRI Shapefile")

        # 9. Szenarien für Gebäudetypologie
        cea_processor.create_scenarios(buildings_gdf, project_paths['building-properties'])

        logger.info(f"✅ Alle Daten erfolgreich gespeichert in: projects/{project_name}/{scenario_name}/")

        return buildings_gdf

    except Exception as e:
        logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}", exc_info=True)
        return None


def main():
    """Hauptfunktion"""
    logger = setup_logger()
    logger.info("🚀 Starte CityGML Verarbeitung")

    citygml_path = project_root / "data/citygml/099082.gml"
    project_name = "CityGMLProject"
    scenario_name = "baseline"

    result = process_citygml(citygml_path, project_name, scenario_name, logger)

    logger.info("\n=== 📊 Verarbeitungszusammenfassung ===")
    logger.info(f"✅ Status: {'Erfolgreich' if result is not None else '❌ Fehlgeschlagen'}")
    if result is not None:
        logger.info(f"🏠 Verarbeitete Gebäude: {len(result)}")

if __name__ == "__main__":
    main()

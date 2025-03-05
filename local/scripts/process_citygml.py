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
from utils.data_sources.fetch_osm_buildings import fetch_surrounding_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_processing.create_site_polygon import create_site_polygon
from utils.data_processing.cea_building_processor import CEABuildingProcessor

def setup_logger(config_path: Path):
    """Initialisiert einen Logger basierend auf Konfiguration"""
    with open(config_path, 'r') as f:
        log_config = yaml.safe_load(f)
    
    log_dir = project_root / log_config['logging']['log_dir']
    log_dir.mkdir(exist_ok=True, parents=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / log_config['logging']['filename_pattern'].format(
        process_name='citygml_processing',
        timestamp=timestamp
    )

    logger = logging.getLogger('CityGMLProcessor')
    logger.setLevel(logging.DEBUG)

    # File Handler
    file_handler = logging.FileHandler(
        log_file, 
        encoding=log_config['logging']['file']['encoding']
    )
    file_handler.setLevel(log_config['logging']['file']['level'])
    file_handler.setFormatter(
        logging.Formatter(log_config['logging']['file']['format'])
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_config['logging']['console']['level'])
    console_handler.setFormatter(
        logging.Formatter(log_config['logging']['console']['format'])
    )

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
        # Lade alle Konfigurationen
        configs = {
            'project': load_config(project_root / "cfg" / "project_config.yml", logger),
            'geometry': load_config(project_root / "cfg" / "geometry" / "geometry_config.yml", logger),
            'wfs': load_config(project_root / "cfg" / "wfs" / "wfs_config.yml", logger),
            'citygml': load_config(project_root / "cfg" / "data_sources" / "vienna_citygml_normalized.yml", logger),
            'cea': load_config(project_root / "cfg" / "cea" / "cea_fields.yml", logger),
            'osm': load_config(project_root / "cfg" / "data_sources" / "osm_config.yml", logger)
        }

        logger.info("\n=== 🏗 CityGML Verarbeitung gestartet ===")

        # 2. Initialisiere CEA Processor & Projektstruktur
        cea_processor = CEABuildingProcessor(configs['citygml'], configs['cea'])
        project_paths = cea_processor.setup_project_structure(project_name, scenario_name, project_root)

        # 3. Verarbeite CityGML zu GeoDataFrame
        buildings_gdf = fetch_citygml_buildings(
            citygml_path, 
            configs['citygml'], 
            configs['cea'],
            logger=logger
        )
        logger.info(f"✅ CityGML verarbeitet: {len(buildings_gdf)} Gebäude")

        if 'geometry' not in buildings_gdf.columns:
            logger.error("❌ FEHLER: buildings_gdf hat KEINE 'geometry'-Spalte nach CityGML-Verarbeitung!")
            logger.info(buildings_gdf.head())  # Debug-Ausgabe
            return None
                
        # 4. Erstelle zuerst Site Polygon für WFS-Abfrage
        site_polygon = create_site_polygon(
            buildings_gdf, 
            buffer_distance=configs['geometry']['site_polygon']['buffer_distance']
        )
        logger.info("✅ Site Polygon erstellt für WFS-Abfrage")

        # 5. WFS Anreicherung mit Site Polygon
        wfs = ViennaWFS(configs['wfs'])
        enriched_buildings_gdf = wfs.enrich_buildings(buildings_gdf, site_polygon)
        logger.info("✅ WFS-Anreicherung abgeschlossen")

        # Überprüfung der Geometrien nach WFS-Anreicherung
        if 'geometry' not in enriched_buildings_gdf.columns:
            logger.error("❌ FEHLER: Geometrien nach WFS-Anreicherung verloren gegangen")
            # Fallback auf original buildings_gdf
            enriched_buildings_gdf = buildings_gdf
            logger.info("⚠️ Verwende originale Gebäudedaten für site_polygon")

        # 6. Hole OSM Gebäude
        osm_buildings = fetch_surrounding_buildings(
            site_polygon,
            config=configs['geometry']
        )
        logger.info(f"✅ OSM Gebäude geladen: {len(osm_buildings)}")

        # 7. Hole OSM Straßen
        osm_streets = fetch_osm_streets(
            site_polygon,
            config={
                'osm': configs['osm'],
                'geometry': configs['geometry']
            }
        )
        logger.info(f"✅ OSM Straßen geladen: {len(osm_streets)}")

        # 8. Speichere Ergebnisse
        cea_processor.save_zone_shapefile(buildings_gdf, project_paths)
        cea_processor.save_typology_shapefile(buildings_gdf, project_paths)

        if not osm_buildings.empty:
            geometry_type = osm_buildings.geometry.iloc[0].geom_type
            osm_buildings.to_file(
                project_paths['geometry'] / "surroundings.shp",
                driver="ESRI Shapefile",
                geometry_type=geometry_type
            )
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
    logger = setup_logger(project_root / "cfg" / "logging" / "logging_config.yml")
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

import sys
from pathlib import Path
import logging
from datetime import datetime

# Projektverzeichnis zum Python-Path hinzufügen
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from utils.setup_project_paths import setup_project_paths, ProjectPaths
from utils.data_sources.fetch_wfs_data import ViennaWFS
from utils.data_sources.fetch_geojson_buildings import GeoJSONBuildingProcessor
from utils.data_sources.fetch_citygml_buildings import CityGMLBuildingProcessor
from utils.data_processing.cea_building_processor import CEABuildingProcessor

def setup_logger():
    """Test-Logger Setup"""
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True, parents=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'pipeline_test_{timestamp}.log'
    
    logger = logging.getLogger('PipelineTest')
    logger.setLevel(logging.DEBUG)
    
    # File Handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def load_config(config_path: Path, logger):
    """Lädt und validiert Konfigurationsdateien"""
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        logger.info(f"✅ Konfiguration geladen: {config_path.name}")
        return config
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden von {config_path}: {str(e)}")
        return None

def test_project_setup(logger):
    """Test der Projektstruktur"""
    logger.info("\n=== Test: Projekt-Setup ===")
    try:
        project_paths = setup_project_paths()
        logger.info("✅ Projektstruktur erstellt:")
        for path_type, path in project_paths.base_path.items():
            logger.info(f"  - {path_type}: {path}")
        return project_paths
    except Exception as e:
        logger.error(f"❌ Fehler beim Projekt-Setup: {str(e)}")
        return None

def test_wfs(logger):
    """Test der WFS-Datenquelle"""
    logger.info("\n=== Test: WFS Datenquelle ===")
    try:
        wfs = ViennaWFS()
        # Beispiel-Bounding Box für Wien
        bbox = (16.3, 48.1, 16.4, 48.2)
        typology = wfs.fetch_building_typology(bbox)
        
        if typology is not None:
            logger.info(f"✅ WFS Daten geladen: {len(typology)} Einträge")
            logger.debug("Beispieldaten:")
            logger.debug(typology.head())
            return typology
        else:
            logger.error("❌ Keine WFS Daten geladen")
            return None
    except Exception as e:
        logger.error(f"❌ Fehler beim WFS-Test: {str(e)}")
        return None

def test_geojson(project_paths, logger):
    """Test der GeoJSON-Verarbeitung"""
    logger.info("\n=== Test: GeoJSON Verarbeitung ===")
    try:
        # Lade Konfigurationen
        geojson_config = load_config(
            project_root / "cfg" / "data_sources" / "ascend_geojson_normalized.yml",
            logger
        )
        cea_config = load_config(
            project_root / "cfg" / "cea" / "cea_fields.yml",
            logger
        )
        
        # Initialisiere Processor
        processor = GeoJSONBuildingProcessor(geojson_config, cea_config)
        
        # Test-GeoJSON Pfad
        geojson_path = project_root / "data" / "geojson" / "ait_gebaeude.geojson"
        
        if not geojson_path.exists():
            logger.warning(f"⚠️ Test-GeoJSON nicht gefunden: {geojson_path}")
            return None
            
        # Verarbeite GeoJSON
        buildings_gdf = processor.create_buildings_dataframe(geojson_path)
        logger.info(f"✅ GeoJSON verarbeitet: {len(buildings_gdf)} Gebäude")
        
        # Korrigierter Aufruf mit allen drei Parametern
        processor.save_zone_shapefile(
            buildings_gdf,  # GeoDataFrame mit Geometrie
            buildings_gdf,  # DataFrame für Zone-Daten
            project_paths   # ProjectPaths Objekt
        )
        processor.save_typology_shapefile(buildings_gdf, project_paths)
        
        return buildings_gdf
    except Exception as e:
        logger.error(f"❌ Fehler beim GeoJSON-Test: {str(e)}")
        return None

def test_citygml(project_paths, logger):
    """Test der CityGML-Verarbeitung"""
    logger.info("\n=== Test: CityGML Verarbeitung ===")
    try:
        # Lade Konfigurationen
        citygml_config = load_config(
            project_root / "cfg" / "data_sources" / "vienna_citygml_normalized.yml",
            logger
        )
        cea_config = load_config(
            project_root / "cfg" / "cea" / "cea_fields.yml",
            logger
        )
        
        # Initialisiere Processor
        processor = CityGMLBuildingProcessor(citygml_config, cea_config)
        
        # Test-CityGML Pfad
        citygml_path = project_root / "data" / "citygml" / "099082.gml"
        
        if not citygml_path.exists():
            logger.warning(f"⚠️ Test-CityGML nicht gefunden: {citygml_path}")
            # Erstelle minimales Test-GML
            create_test_citygml(citygml_path)
            
        # Verarbeite CityGML
        buildings_df = processor.create_buildings_dataframe(citygml_path)
        logger.info(f"✅ CityGML verarbeitet: {len(buildings_df)} Gebäude")
        
        # Korrigierte Aufrufe
        processor.save_zone_shapefile(buildings_df, buildings_df, project_paths)  # buildings_df zweimal, da es sowohl GDF als auch Zone-DF enthält
        processor.save_typology_shapefile(buildings_df, project_paths)
        
        return buildings_df
    except Exception as e:
        logger.error(f"❌ Fehler beim CityGML-Test: {str(e)}")
        return None

def create_test_citygml(path):
    """Erstellt eine minimale Test-CityGML Datei"""
    minimal_citygml = """<?xml version="1.0" encoding="UTF-8"?>
    <CityModel xmlns="http://www.opengis.net/citygml/1.0">
        <cityObjectMember>
            <bldg:Building>
                <bldg:measuredHeight>10.0</bldg:measuredHeight>
                <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
            </bldg:Building>
        </cityObjectMember>
    </CityModel>
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(minimal_citygml)

def main():
    # Setup Logger
    logger = setup_logger()
    logger.info("🚀 Starte Pipeline-Tests")
    
    # Teste Projekt-Setup
    project_paths = test_project_setup(logger)
    if project_paths is None:
        logger.error("❌ Projekt-Setup fehlgeschlagen, breche Tests ab")
        return
    
    # Teste WFS
    wfs_data = test_wfs(logger)
    
    # Teste GeoJSON
    geojson_data = test_geojson(project_paths, logger)
    
    # Teste CityGML
    citygml_data = test_citygml(project_paths, logger)
    
    # Zusammenfassung
    logger.info("\n=== Testzusammenfassung ===")
    logger.info(f"WFS Test: {'✅' if wfs_data is not None else '❌'}")
    logger.info(f"GeoJSON Test: {'✅' if geojson_data is not None else '❌'}")
    logger.info(f"CityGML Test: {'✅' if citygml_data is not None else '❌'}")

if __name__ == "__main__":
    main() 
"""
Integrationstests für den gesamten Verarbeitungsablauf.
"""
import pytest
import geopandas as gpd
from pathlib import Path
import tempfile
import shutil
from core.project_manager import ProjectManager
from core.config_manager import load_config
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings
from pipeline.data_sources.wfs_fetcher import ViennaWFS
from pipeline.processing.cea_processor import CEABuildingProcessor

@pytest.fixture
def test_project_dir(tmp_path):
    """Erstellt ein temporäres Test-Verzeichnis."""
    return tmp_path

@pytest.fixture
def test_config():
    """Erstellt eine Test-Konfiguration."""
    return {
        'crs': 'EPSG:31256',
        'data_source': {
            'citygml': {
                'base_path': 'data/raw/citygml',
                'default_file': 'test.gml',
                'test_file': 'tests/data/test.gml'
            },
            'wfs': {
                'url': 'https://data.wien.gv.at/daten/geo',
                'version': '2.0.0',
                'timeout': 30,
                'srs': 'EPSG:31256',
                'streams': [
                    {'name': 'test_stream1', 'layer': 'test_layer1'},
                    {'name': 'test_stream2', 'layer': 'test_layer2'}
                ]
            }
        },
        'processing': {
            'cea': {
                'config': 'config/cea/mapping.yml'
            }
        },
        'outputs': {
            'citygml': 'outputs/citygml',
            'data': 'outputs/data'
        },
        'scenario': 'test_scenario'
    }

def test_complete_workflow(test_project_dir, test_config):
    """Testet den gesamten Verarbeitungsablauf."""
    # 1. Projekt initialisieren
    project_manager = ProjectManager("test_project", "test_scenario")
    assert project_manager.setup_project_structure(test_project_dir)
    
    # 2. CityGML verarbeiten
    citygml_path = test_config['data_source']['citygml']['test_file']
    buildings_gdf = fetch_citygml_buildings(citygml_path, test_project_dir, test_config)
    assert buildings_gdf is not None
    assert not buildings_gdf.empty
    
    # 3. WFS-Daten abrufen
    wfs = ViennaWFS(test_config['data_source']['wfs'])
    bbox = buildings_gdf.total_bounds
    wfs_data = wfs.process_streams(bbox)
    assert wfs_data is not None
    
    # 4. CEA-Verarbeitung
    cea_processor = CEABuildingProcessor(test_config['processing']['cea'], test_config)
    assert cea_processor is not None
    
    # 5. Ergebnisse validieren
    required_files = [
        'inputs/building-geometry/zone.shp',
        'inputs/building-properties/typology.dbf',
        'inputs/networks/streets.shp',
        'inputs/building-geometry/surroundings.shp',
        'inputs/building-geometry/site.shp'
    ]
    
    for file_path in required_files:
        assert (test_project_dir / file_path).exists() 
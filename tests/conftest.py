"""
Gemeinsame Test-Fixtures und Konfiguration.
"""
import pytest
import os
import sys
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
from core.config_manager import load_config
from core.project_paths import get_config_path, get_output_path

# Füge das Projekt-Root-Verzeichnis zum Python-Pfad hinzu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture(autouse=True)
def setup_test_env():
    """Richtet die Test-Umgebung ein."""
    # Setze Umgebungsvariablen für Tests
    os.environ["TESTING"] = "true"
    yield
    # Cleanup nach den Tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

@pytest.fixture(scope="session")
def test_data_dir():
    """Basis-Verzeichnis für Testdaten."""
    return Path(__file__).parent / "data"

@pytest.fixture(scope="session")
def test_fixtures_dir():
    """Basis-Verzeichnis für Test-Fixtures."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def test_outputs_dir():
    """Basis-Verzeichnis für Test-Ausgaben."""
    return Path(__file__).parent / "outputs"

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(test_data_dir, test_fixtures_dir, test_outputs_dir):
    """Richtet die Testumgebung ein."""
    # Erstelle Verzeichnisse
    for directory in [test_data_dir, test_fixtures_dir, test_outputs_dir]:
        directory.mkdir(exist_ok=True)
        
    # Erstelle Unterverzeichnisse für verschiedene Datenquellen
    (test_fixtures_dir / "citygml").mkdir(exist_ok=True)
    (test_fixtures_dir / "osm").mkdir(exist_ok=True)
    (test_fixtures_dir / "wfs").mkdir(exist_ok=True)
    
    # Erstelle Ausgabeverzeichnisse
    (test_outputs_dir / "citygml").mkdir(exist_ok=True)
    (test_outputs_dir / "osm").mkdir(exist_ok=True)
    (test_outputs_dir / "3dtiles").mkdir(exist_ok=True)
    (test_outputs_dir / "geojson").mkdir(exist_ok=True)

@pytest.fixture
def global_config():
    """Lädt die globale Testkonfiguration."""
    config_path = get_config_path() / "global.yml"
    return load_config(config_path)

@pytest.fixture
def citygml_config(global_config):
    """CityGML-spezifische Konfiguration."""
    return global_config.get('citygml', {})

@pytest.fixture
def osm_config(global_config):
    """OSM-spezifische Konfiguration."""
    return global_config.get('osm', {})

@pytest.fixture
def wfs_config(global_config):
    """WFS-spezifische Konfiguration."""
    return global_config.get('wfs', {})

@pytest.fixture
def sample_site_gdf():
    """Erstellt ein Beispiel-Site-Polygon für Tests."""
    # Erstelle ein einfaches Polygon
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    return gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")

@pytest.fixture
def sample_buildings_gdf():
    """Erstellt Beispiel-Gebäude für Tests."""
    # Erstelle einige Beispiel-Gebäude
    buildings = [
        Polygon([(0, 0), (0, 20), (20, 20), (20, 0), (0, 0)]),
        Polygon([(30, 30), (30, 50), (50, 50), (50, 30), (30, 30)]),
        Polygon([(60, 60), (60, 80), (80, 80), (80, 60), (60, 60)])
    ]
    return gpd.GeoDataFrame(geometry=buildings, crs="EPSG:31256")

@pytest.fixture
def sample_osm_config():
    """Erstellt eine Beispiel-OSM-Konfiguration für Tests."""
    return {
        'buildings': {
            'buffer_distance': 100,
            'defaults': {
                'height': 10,
                'floors': 3,
                'year': 1990,
                'category': 'residential',
                'REFERENCE': ''
            }
        }
    }

@pytest.fixture
def sample_street_config():
    """Erstellt eine Beispiel-Straßen-Konfiguration für Tests."""
    return {
        'street_types': {
            'primary': True,
            'secondary': True,
            'tertiary': True,
            'residential': True
        },
        'network_type': 'all',
        'buffer_distance': 100
    }

@pytest.fixture
def sample_global_config():
    """Erstellt eine Beispiel-Global-Konfiguration für Tests."""
    return {
        'paths': {
            'outputs': {
                'buildings': 'outputs/buildings',
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        },
        'processing': {
            'site_polygon': {
                'buffer_distance': 3
            }
        }
    } 
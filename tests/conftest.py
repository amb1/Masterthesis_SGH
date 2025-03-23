"""
Gemeinsame Test-Fixtures und Konfiguration.
"""
import pytest
import os
import sys
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon

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

@pytest.fixture
def test_data_dir():
    """Gibt das Test-Datenverzeichnis zurück."""
    return Path(__file__).parent / "test_data"

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
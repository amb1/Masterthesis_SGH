"""
Fixtures für CEA-Tests.

Dieses Modul enthält wiederverwendbare Fixtures für CEA-bezogene Tests.
"""

import pytest
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
import pandas as pd

@pytest.fixture
def sample_building_data():
    """Erstellt ein Sample-GeoDataFrame mit Gebäudedaten für Tests."""
    geometry = [Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])]
    data = {
        'building_id': ['B001'],
        'construction_period': ['1900-1920'],
        'height': [10.0],
        'floors': [3],
        'geometry': geometry
    }
    return gpd.GeoDataFrame(data, crs='EPSG:2056')

@pytest.fixture
def sample_wfs_data():
    """Erstellt Sample-WFS-Daten für Tests."""
    return {
        'buildings': {
            'features': [
                {
                    'properties': {
                        'building_id': 'B001',
                        'year_built': 1910,
                        'usage': 'residential'
                    }
                }
            ]
        }
    }

@pytest.fixture
def sample_config():
    """Erstellt eine Sample-Konfiguration für Tests."""
    return {
        'citygml': {
            'building_types': {
                'residential': {
                    'periods': {
                        '1900-1920': {'year': 1910}
                    }
                }
            }
        },
        'wfs': {
            'layers': ['buildings']
        }
    }

@pytest.fixture
def temp_scenario_path(tmp_path):
    """Erstellt einen temporären Szenario-Pfad für Tests."""
    scenario_path = tmp_path / "scenario"
    scenario_path.mkdir()
    return scenario_path 
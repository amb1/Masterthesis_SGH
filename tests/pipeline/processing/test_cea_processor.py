"""
Unit-Tests für die CEA-Utils.
"""

import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.processing.cea_processor import CEABuildingProcessor

@pytest.fixture
def sample_config():
    """Beispielkonfiguration für Tests."""
    return {
        'cea': {
            'period_ranges': {
                '1848-1918': [1848, 1918],
                '1919-1945': [1919, 1945],
                '1946-1960': [1946, 1960],
                '1961-1976': [1961, 1976],
                '1977-1989': [1977, 1989],
                '1990-2002': [1990, 2002],
                '2003-2009': [2003, 2009],
                '2010-2020': [2010, 2020]
            },
            'building_periods': [
                {'start': 1800, 'end': 1918, 'suffix': '_B'},
                {'start': 1919, 'end': 1945, 'suffix': '_C'}
            ],
            'defaults': {
                'height': 10.0,
                'floors': 3,
                'year_built': 1950
            }
        }
    }

@pytest.fixture
def processor(sample_config):
    """Erstellt eine Instanz des CEA-Prozessors"""
    return CEABuildingProcessor(sample_config)

@pytest.fixture
def sample_buildings_gdf():
    """Beispiel-GeoDataFrame für Tests."""
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    data = {
        'geometry': [geometry],
        'Name': ['Test Building'],
        'height_m': [10.5],
        'year_built': [1950]
    }
    return gpd.GeoDataFrame(data, crs='EPSG:4326')

@pytest.fixture
def sample_wfs_data():
    """Beispiel-WFS-Daten für Tests."""
    return {
        'buildings': {
            'features': [
                {
                    'properties': {
                        'id': '1',
                        'year_built': 1900,
                        'building_type': 'residential'
                    }
                },
                {
                    'properties': {
                        'id': '2',
                        'year_built': 1930,
                        'building_type': 'commercial'
                    }
                }
            ]
        }
    }

def test_get_year_and_suffix_known_range(sample_config):
    """Test get_year_and_suffix mit bekanntem Zeitraum."""
    year, suffix = get_year_and_suffix("1848-1918", sample_config)
    assert 1848 <= year <= 1918
    assert suffix == "_B"

def test_get_year_and_suffix_unknown_range(sample_config):
    """Test get_year_and_suffix mit unbekanntem Zeitraum."""
    year, suffix = get_year_and_suffix("2000-2020", sample_config)
    assert year == 2000  # Sollte den Startwert nehmen
    assert suffix == "_I"  # Sollte den Default-Suffix nehmen

def test_adjust_field_widths(sample_buildings_gdf):
    """Test adjust_field_widths mit Beispieldaten."""
    # Füge problematische Felder hinzu
    sample_buildings_gdf['Gebäudemo'] = 'Test'
    sample_buildings_gdf['Gebäudein'] = 'Test'
    
    adjusted_gdf = adjust_field_widths(sample_buildings_gdf)
    assert 'Gebäudemo' not in adjusted_gdf.columns
    assert 'Gebäudein' not in adjusted_gdf.columns
    assert 'Name' in adjusted_gdf.columns  # Originale Felder bleiben erhalten

def test_enrich_building_data(sample_buildings_gdf, sample_wfs_data):
    """Test enrich_building_data mit Beispieldaten."""
    enriched_gdf = enrich_building_data(sample_buildings_gdf, sample_wfs_data)
    
    # Prüfe, ob neue Felder hinzugefügt wurden
    assert 'buildings_id' in enriched_gdf.columns
    assert 'buildings_year_built' in enriched_gdf.columns
    assert 'buildings_building_type' in enriched_gdf.columns
    
    # Prüfe die Werte
    assert enriched_gdf['buildings_year_built'].iloc[0] == 1900
    assert enriched_gdf['buildings_building_type'].iloc[0] == 'residential'

@pytest.mark.parametrize("field_name,expected_type", [
    ("Name", str),
    ("height_m", float)
])
def test_field_types_after_adjustment(sample_buildings_gdf, field_name, expected_type):
    """Test die Feldtypen nach der Anpassung."""
    adjusted_gdf = adjust_field_widths(sample_buildings_gdf)
    assert isinstance(adjusted_gdf[field_name].iloc[0], expected_type)

def test_process_building(processor, sample_buildings_gdf):
    """Test für die Verarbeitung eines einzelnen Gebäudes"""
    building_data = {
        'geometry': sample_buildings_gdf.iloc[0].geometry,
        'properties': {
            'Name': 'Test Building',
            'height_m': 10.5,
            'year_built': 1950
        }
    }
    
    result = processor.process_building(building_data)
    
    assert result is not None
    assert 'Name' in result
    assert result['height_m'] == 10.5
    assert result['year_built'] == 1950

def test_validate_building(processor, sample_buildings_gdf):
    """Test für die Validierung eines Gebäudes"""
    building_data = {
        'geometry': sample_buildings_gdf.iloc[0].geometry,
        'properties': {
            'Name': 'Test Building',
            'height_m': 10.5,
            'year_built': 1950
        }
    }
    
    assert processor.validate_building(building_data) is True 
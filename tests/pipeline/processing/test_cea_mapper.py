"""
Unit-Tests für die CEA-Mapping-Funktionen.
"""

import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.processing.cea_mapper import get_year_and_suffix, adjust_field_widths, enrich_building_data

@pytest.fixture
def sample_config():
    """Beispielkonfiguration für Tests."""
    return {
        'period_ranges': {
            '1848-1918': [1848, 1918],
            '1919-1945': [1919, 1945],
            '1946-1960': [1946, 1960]
        },
        'building_periods': [
            {'start': 1800, 'end': 1918, 'suffix': '_B'},
            {'start': 1919, 'end': 1945, 'suffix': '_C'},
            {'start': 1946, 'end': 1960, 'suffix': '_D'}
        ]
    }

@pytest.fixture
def sample_buildings_gdf():
    """Beispiel-GeoDataFrame für Tests."""
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    data = {
        'geometry': [geometry],
        'Gebäudemo': ['Test'],
        'Gebäudein': ['Info'],
        'valid_field': ['Data']
    }
    return gpd.GeoDataFrame(data, geometry='geometry')

@pytest.fixture
def sample_wfs_data():
    """Beispiel-WFS-Daten für Tests."""
    return {
        'layer1': {
            'features': [{
                'properties': {
                    'height': 10.5,
                    'year_built': 1950
                }
            }]
        }
    }

def test_get_year_and_suffix_with_valid_period(sample_config):
    """Test: get_year_and_suffix mit gültiger Bauperiode."""
    year, suffix = get_year_and_suffix('1848-1918', sample_config)
    assert 1848 <= year <= 1918
    assert suffix == '_B'

def test_get_year_and_suffix_with_invalid_period(sample_config):
    """Test: get_year_and_suffix mit ungültiger Bauperiode."""
    year, suffix = get_year_and_suffix('invalid', sample_config)
    assert year == 2000
    assert suffix == '_I'

def test_get_year_and_suffix_with_none(sample_config):
    """Test: get_year_and_suffix mit None als Periode."""
    year, suffix = get_year_and_suffix(None, sample_config)
    assert year == 2000
    assert suffix == '_I'

def test_adjust_field_widths(sample_buildings_gdf):
    """Test: adjust_field_widths entfernt problematische Felder."""
    adjusted_gdf = adjust_field_widths(sample_buildings_gdf)
    
    # Prüfe ob problematische Felder entfernt wurden
    assert 'Gebäudemo' not in adjusted_gdf.columns
    assert 'Gebäudein' not in adjusted_gdf.columns
    
    # Prüfe ob valide Felder erhalten bleiben
    assert 'valid_field' in adjusted_gdf.columns
    assert 'geometry' in adjusted_gdf.columns

def test_enrich_building_data_with_valid_data(sample_buildings_gdf, sample_wfs_data):
    """Test: enrich_building_data mit gültigen WFS-Daten."""
    enriched_gdf = enrich_building_data(sample_buildings_gdf, sample_wfs_data)
    
    # Prüfe ob WFS-Daten hinzugefügt wurden
    assert 'layer1_height' in enriched_gdf.columns
    assert 'layer1_year_built' in enriched_gdf.columns
    assert enriched_gdf.at[0, 'layer1_height'] == 10.5
    assert enriched_gdf.at[0, 'layer1_year_built'] == 1950

def test_enrich_building_data_with_empty_wfs_data(sample_buildings_gdf):
    """Test: enrich_building_data mit leeren WFS-Daten."""
    enriched_gdf = enrich_building_data(sample_buildings_gdf, {})
    
    # Prüfe ob Original-GeoDataFrame unverändert zurückgegeben wird
    assert list(enriched_gdf.columns) == list(sample_buildings_gdf.columns)
    assert len(enriched_gdf) == len(sample_buildings_gdf)

def test_enrich_building_data_with_invalid_layer(sample_buildings_gdf, sample_wfs_data):
    """Test: enrich_building_data mit ungültigem WFS-Layer."""
    # Füge ungültigen Layer hinzu
    sample_wfs_data['invalid_layer'] = None
    
    enriched_gdf = enrich_building_data(sample_buildings_gdf, sample_wfs_data)
    
    # Prüfe ob valide Daten trotzdem verarbeitet wurden
    assert 'layer1_height' in enriched_gdf.columns
    assert 'layer1_year_built' in enriched_gdf.columns 
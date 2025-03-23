"""
Unit-Tests für den CEA-Gebäudeprozessor.
"""

import pytest
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point
from pathlib import Path
from unittest.mock import MagicMock, patch
from pipeline.processing.cea_processor import CEABuildingProcessor

@pytest.fixture
def sample_config():
    """Beispielkonfiguration für Tests."""
    return {
        'project': {
            'paths': {
                'output': 'local/data/outputs'
            }
        },
        'cea': {
            'config': 'cea/test_config.yml',
            'mapping': {
                'periods': {
                    '1848-1918': {
                        'categories': ['_B'],
                        'default_year': 1900
                    }
                },
                'building_types': {
                    'standard_prefix': {
                        'WOHNGEBAEUDE': 'MFH',
                        'BUEROGEBAEUDE': 'OFFICE'
                    }
                },
                'defaults': {
                    'floors_ag': 4,
                    'floors_bg': 1,
                    'year': 1960,
                    'use_type': 'NONE'
                },
                'field_mappings': {
                    'floors_ag': {
                        'source': 'measured_height',
                        'calculation': 'value / 3'
                    },
                    'floors_bg': {
                        'source': 'NS',
                        'mapping': {'1': 1, '2': 2, '*': 1}
                    },
                    'year': {
                        'sources': [
                            {'field': 'L_BAUJ', 'type': 'direct'},
                            {'field': 'OBJ_STR2_TXT', 'type': 'period_mapping'}
                        ]
                    },
                    'use_type': {
                        'sources': [
                            {'field': 'L_BAUTYP'},
                            {'field': 'BAUTYP_TXT'}
                        ]
                    }
                }
            }
        },
        'crs': 'EPSG:31256'
    }

@pytest.fixture
def sample_buildings_gdf():
    """Beispiel-GeoDataFrame für Tests."""
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    data = {
        'geometry': [geometry],
        'measured_height': [12.0],
        'NS': ['1'],
        'L_BAUJ': [1950],
        'L_BAUTYP': ['WOHNGEBAEUDE'],
        'OBJ_STR2_TXT': ['1848-1918']
    }
    return gpd.GeoDataFrame(data, geometry='geometry')

@pytest.fixture
def processor(sample_config):
    """Erstellt eine Instanz des CEA-Prozessors."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pipeline.processing.base_processor.BuildingProcessorInterface.load_config', 
               return_value=sample_config['cea']):
        return CEABuildingProcessor(sample_config)

def test_init_with_valid_config(sample_config):
    """Test: Initialisierung mit gültiger Konfiguration."""
    with patch('pathlib.Path.exists', return_value=True), \
         patch('pipeline.processing.base_processor.BuildingProcessorInterface.load_config', 
               return_value=sample_config['cea']):
        processor = CEABuildingProcessor(sample_config)
        assert processor.cea_config is not None
        assert processor.cea_config == sample_config['cea']

def test_init_with_invalid_config():
    """Test: Initialisierung mit ungültiger Konfiguration."""
    with pytest.raises(ValueError, match="❌ Keine gültige CEA-Konfiguration gefunden"):
        CEABuildingProcessor({})

def test_map_construction_period(processor):
    """Test: Mapping von Bauperioden."""
    # Test mit gültiger Periode
    period = "1848-1918"
    result = processor._map_construction_period(period)
    assert result == "_B"
    
    # Test mit ungültiger Periode
    period = "1919-1944"
    result = processor._map_construction_period(period)
    assert result == ""

def test_get_year_from_period(processor):
    """Test: Berechnung des Jahres aus der Bauperiode."""
    # Test mit gültiger Periode
    period = "1848-1918"
    result = processor._get_year_from_period(period)
    assert result == 1900
    
    # Test mit ungültiger Periode
    period = "1919-1944"
    result = processor._get_year_from_period(period)
    assert result == processor.cea_config['mapping']['defaults']['year']

def test_map_building_type(processor):
    """Test: Mapping von Gebäudetypen."""
    # Test mit gültigem Typ
    building_type = "WOHNGEBAEUDE"
    result = processor._map_building_type(building_type)
    assert result == "MFH"
    
    # Test mit ungültigem Typ
    building_type = "UNBEKANNT"
    result = processor._map_building_type(building_type)
    assert result == "NONE"

def test_create_standard_value(processor):
    """Test: Erstellung von Standardwerten."""
    # Test mit gültigen Werten
    period = "1848-1918"
    building_type = "WOHNGEBAEUDE"
    result = processor._create_standard_value(period, building_type)
    assert result == "MFH_B"
    
    # Test mit ungültigen Werten
    period = "1919-1944"
    building_type = "UNBEKANNT"
    result = processor._create_standard_value(period, building_type)
    assert result == "NONE"

def test_validate_building(processor, sample_buildings_gdf):
    """Test: Validierung von Gebäudedaten."""
    # Test mit gültigen Daten
    building_data = {
        'geometry': sample_buildings_gdf.iloc[0].geometry,
        'measured_height': 12.0,
        'NS': '1',
        'L_BAUJ': 1950,
        'L_BAUTYP': 'WOHNGEBAEUDE',
        'OBJ_STR2_TXT': '1848-1918'
    }
    assert processor.validate_building(building_data) is True
    
    # Test mit ungültigen Daten
    invalid_data = {}
    assert processor.validate_building(invalid_data) is False

def test_process_building(processor, sample_buildings_gdf):
    """Test: Verarbeitung eines Gebäudes."""
    # Test mit gültigen Daten
    building_data = {
        'geometry': sample_buildings_gdf.iloc[0].geometry,
        'measured_height': 12.0,
        'NS': '1',
        'L_BAUJ': 1950,
        'L_BAUTYP': 'WOHNGEBAEUDE',
        'OBJ_STR2_TXT': '1848-1918'
    }
    result = processor.process_building(building_data)
    assert result is not None
    assert 'floors_ag' in result
    assert 'floors_bg' in result
    assert 'year' in result
    assert 'use_type' in result
    
    # Test mit ungültigen Daten
    invalid_data = {}
    result = processor.process_building(invalid_data)
    assert result == invalid_data

@patch('pathlib.Path')
def test_create_cea_files(mock_path, processor, sample_buildings_gdf, tmp_path):
    """Test: Erstellung von CEA-Dateien."""
    # Mock für temporäre Verzeichnisse
    geometry_dir = tmp_path / "geometry"
    properties_dir = tmp_path / "properties"
    geometry_dir.mkdir(parents=True)
    properties_dir.mkdir(parents=True)
    
    # Test mit gültigen Daten
    zone_gdf, typology_gdf = processor._create_cea_files(geometry_dir, properties_dir)
    assert isinstance(zone_gdf, gpd.GeoDataFrame)
    assert isinstance(typology_gdf, gpd.GeoDataFrame)
    assert not zone_gdf.empty
    assert not typology_gdf.empty

def test_validate_geometry(processor):
    """Test: Validierung von Geometrien."""
    # Test mit gültiger Geometrie
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf = gpd.GeoDataFrame({'geometry': [geometry]})
    assert processor.validate_geometry(gdf, ['Polygon']) is True
    
    # Test mit ungültiger Geometrie
    point = Point(0, 0)
    gdf = gpd.GeoDataFrame({'geometry': [point]})
    assert processor.validate_geometry(gdf, ['Polygon']) is False

def test_validate_fields(processor):
    """Test: Validierung von Feldern."""
    # Test mit gültigen Feldern
    data = {
        'geometry': [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])],
        'field1': [1],
        'field2': ['test']
    }
    gdf = gpd.GeoDataFrame(data)
    assert processor.validate_fields(gdf, ['field1', 'field2']) is True
    
    # Test mit fehlenden Feldern
    assert processor.validate_fields(gdf, ['field3']) is False

def test_validate_crs(processor):
    """Test: Validierung des Koordinatensystems."""
    # Test mit gültigem CRS
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs='EPSG:31256')
    assert processor.validate_crs(gdf, 'EPSG:31256') is True
    
    # Test mit ungültigem CRS
    gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs='EPSG:4326')
    assert processor.validate_crs(gdf, 'EPSG:31256') is False 
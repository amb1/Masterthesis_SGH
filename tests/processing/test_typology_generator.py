"""Tests für den TypologyGenerator."""

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from pipeline.processing.typology_generator import TypologyGenerator

@pytest.fixture
def sample_config():
    return {
        'processing': {
            'file_formats': {
                'shp_driver': 'ESRI Shapefile'
            }
        }
    }

@pytest.fixture
def sample_buildings():
    # Erstelle Testgebäude mit verschiedenen Attributen
    geometries = [
        Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
        Polygon([(2, 0), (2, 1), (3, 1), (3, 0)])
    ]
    
    data = {
        'building_id': ['B1', 'B2'],
        'year_of_construction': [1900, 1960],
        'height': [10.5, 15.2],
        'floors': [3, 4],
        'building_type': ['RESIDENTIAL', 'COMMERCIAL'],
        'geometry': geometries
    }
    
    return gpd.GeoDataFrame(data, crs='EPSG:31256')

def test_create_typology(sample_config, sample_buildings):
    generator = TypologyGenerator(sample_config)
    typology_gdf = generator.create_typology(sample_buildings)
    
    assert isinstance(typology_gdf, gpd.GeoDataFrame)
    assert len(typology_gdf) == len(sample_buildings)
    assert typology_gdf.crs == sample_buildings.crs
    
    # Prüfe die generierten Attribute
    assert all(col in typology_gdf.columns for col in [
        'building_id', 'year_built', 'height', 'floors',
        'use_type', 'construction_type'
    ])
    
    # Prüfe die Konstruktionstypen
    assert typology_gdf.loc[0, 'construction_type'] == 'HISTORICAL'  # 1900
    assert typology_gdf.loc[1, 'construction_type'] == 'MODERN'      # 1960

def test_create_typology_empty_input(sample_config):
    generator = TypologyGenerator(sample_config)
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs='EPSG:31256')
    
    with pytest.raises(ValueError, match="Keine Gebäude für Typology-Erstellung vorhanden"):
        generator.create_typology(empty_gdf)

def test_determine_construction_type(sample_config):
    generator = TypologyGenerator(sample_config)
    
    test_cases = [
        ({'year_of_construction': 1900}, 'HISTORICAL'),
        ({'year_of_construction': 1930}, 'TRADITIONAL'),
        ({'year_of_construction': 1960}, 'MODERN'),
        ({'year_of_construction': 2000}, 'CONTEMPORARY'),
        ({}, 'CONTEMPORARY')  # Standardfall ohne Jahr
    ]
    
    for building_data, expected_type in test_cases:
        building = pd.Series(building_data)
        assert generator._determine_construction_type(building) == expected_type

def test_export_typology(sample_config, sample_buildings, tmp_path):
    generator = TypologyGenerator(sample_config)
    typology_gdf = generator.create_typology(sample_buildings)
    
    output_path = tmp_path / "typology.shp"
    generator.export_typology(typology_gdf, str(output_path))
    
    assert output_path.exists()
    
    # Prüfe, ob die exportierte Datei wieder eingelesen werden kann
    loaded_gdf = gpd.read_file(str(output_path))
    assert len(loaded_gdf) == len(typology_gdf) 
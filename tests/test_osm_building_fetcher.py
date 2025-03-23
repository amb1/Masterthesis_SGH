import pytest
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, box
from pathlib import Path
import os
from unittest.mock import patch, MagicMock
from pipeline.data_sources.osm_building_fetcher import (
    fetch_surrounding_buildings,
    process_osm_buildings,
    save_surrounding_buildings,
    fetch_osm_buildings,
    main
)
import tempfile
from osmnx._errors import InsufficientResponseError
import pandas as pd

@pytest.fixture
def sample_site_gdf():
    """Erstellt ein Beispiel-Site-Polygon für Tests."""
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    return gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")

@pytest.fixture
def sample_config():
    """Erstellt eine Beispiel-Konfiguration für Tests."""
    return {
        'buildings': {
            'buffer_distance': 100,
            'defaults': {
                'height': 10,
                'floors': 3,
                'year': 1990
            }
        }
    }

@pytest.fixture
def mock_buildings_data():
    """Erstellt Mock-OSM-Gebäudedaten für Tests"""
    # Erstelle zwei Beispiel-Gebäude
    building1 = Polygon([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])
    building2 = Polygon([(20, 20), (20, 30), (30, 30), (30, 20), (20, 20)])
    
    # Erstelle GeoDataFrame mit den Gebäuden
    buildings_gdf = gpd.GeoDataFrame(
        {
            'building': ['yes', 'residential'],
            'height': [15, 12],
            'building:levels': [4, 3],
            'start_date': [1985, 2000],
            'geometry': [building1, building2]
        },
        crs="EPSG:31256"
    )
    return buildings_gdf

@pytest.fixture
def sample_buildings_data():
    """Beispiel-Gebäudedaten für Tests"""
    geometry = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])
    ]
    data = {
        'geometry': geometry,
        'building': ['yes', 'yes'],
        'height': [10.5, 15.2],
        'building:levels': [3, 4],
        'start_date': ['1950', '1980']
    }
    return gpd.GeoDataFrame(data, crs='EPSG:4326')

@pytest.fixture
def mock_osmnx():
    """Mock für osmnx Funktionen"""
    with patch('pipeline.data_sources.osm_building_fetcher.ox') as mock_ox:
        mock_ox.geometries_from_polygon = MagicMock(return_value=sample_buildings_data())
        yield mock_ox

def test_fetch_surrounding_buildings(mock_osmnx, sample_buildings_data):
    """Test fetch_surrounding_buildings mit gemockten Daten"""
    site_polygon = box(0, 0, 1, 1)
    site_gdf = gpd.GeoDataFrame({'geometry': [site_polygon]}, crs='EPSG:4326')
    
    result = fetch_surrounding_buildings(site_gdf)
    
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 2
    assert all(col in result.columns for col in ['height', 'building:levels', 'start_date'])

def test_process_osm_buildings(mock_buildings_data):
    """Test der process_osm_buildings Funktion"""
    defaults = {
        'height': 10,
        'floors': 3,
        'year': 1990
    }
    
    result = process_osm_buildings(mock_buildings_data, defaults)
    
    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs == mock_buildings_data.crs
    assert len(result) == 2
    assert all(col in result.columns for col in ['height', 'floors', 'year'])
    assert result['height'].iloc[0] == 15  # Originaler Wert beibehalten
    assert result['floors'].iloc[0] == 4   # Originaler Wert beibehalten
    assert result['year'].iloc[0] == 1985  # Aus start_date übernommen

def test_save_surrounding_buildings(mock_buildings_data):
    """Test der save_surrounding_buildings Funktion"""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / 'buildings.shp'
        save_surrounding_buildings(mock_buildings_data, output_path)
        
        assert output_path.exists()
        saved_gdf = gpd.read_file(output_path)
        assert isinstance(saved_gdf, gpd.GeoDataFrame)
        assert len(saved_gdf) == len(mock_buildings_data)

def test_fetch_osm_buildings(sample_site_gdf, mock_buildings_data):
    """Test der fetch_osm_buildings Funktion"""
    with patch('pipeline.data_sources.osm_building_fetcher.ox.geometries_from_polygon', return_value=mock_buildings_data):
        result = fetch_osm_buildings(sample_site_gdf)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.crs == sample_site_gdf.crs
        assert len(result) == 2
        assert all(col in result.columns for col in ['height', 'floors', 'year'])

def test_main():
    """Test der Hauptfunktion"""
    # Mock-Konfigurationen
    osm_config = {
        'buildings': {
            'buffer_distance': 100,
            'defaults': {
                'height': 10,
                'floors': 3,
                'year': 1990
            }
        }
    }
    
    global_config = {
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'buildings': 'outputs/buildings'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_building_fetcher.load_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_building_fetcher.load_yaml_config', return_value=global_config), \
         patch('pipeline.data_sources.osm_building_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_building_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_building_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_building_fetcher.fetch_osm_buildings', return_value=mock_site), \
         patch('pipeline.data_sources.osm_building_fetcher.process_osm_buildings', return_value=mock_site), \
         patch('pipeline.data_sources.osm_building_fetcher.save_surrounding_buildings'):
        
        # Führe die Hauptfunktion aus
        main()

def test_fetch_surrounding_buildings_no_crs():
    """Test der fetch_surrounding_buildings Funktion ohne CRS"""
    # Erstelle ein GeoDataFrame ohne CRS
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[polygon])
    
    config = {
        'buildings': {
            'buffer_distance': 100
        }
    }
    
    # Mock OSM-Daten
    mock_buildings = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])],
        crs="EPSG:4326"
    )
    
    with patch('pipeline.data_sources.osm_building_fetcher.ox.geometries_from_polygon', return_value=mock_buildings):
        result = fetch_surrounding_buildings(site_gdf, config)
        assert result.crs == "EPSG:31256"

def test_fetch_surrounding_buildings_empty_input():
    """Test der fetch_surrounding_buildings Funktion mit leerem Input"""
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")
    config = {'buildings': {'buffer_distance': 100}}
    
    result = fetch_surrounding_buildings(empty_gdf, config)
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0
    assert result.crs == "EPSG:4326"

def test_fetch_surrounding_buildings_invalid_config():
    """Test der fetch_surrounding_buildings Funktion mit ungültiger Konfiguration"""
    site_gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])],
        crs="EPSG:31256"
    )
    
    invalid_config = "keine gültige config"
    
    result = fetch_surrounding_buildings(site_gdf, invalid_config)
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0
    assert result.crs == "EPSG:4326"

def test_process_osm_buildings_empty_input():
    """Test der process_osm_buildings Funktion mit leerem Input"""
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")
    defaults = {'height': 10, 'floors': 3, 'year': 1990}
    
    result = process_osm_buildings(empty_gdf, defaults)
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 0
    assert result.crs == "EPSG:31256"

def test_process_osm_buildings_missing_attributes():
    """Test der process_osm_buildings Funktion mit fehlenden Attributen"""
    buildings_gdf = gpd.GeoDataFrame(
        geometry=[Polygon([(0, 0), (0, 10), (10, 10), (10, 0), (0, 0)])],
        crs="EPSG:31256"
    )
    
    defaults = {'height': 10, 'floors': 3, 'year': 1990}
    
    result = process_osm_buildings(buildings_gdf, defaults)
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 1
    assert result['height'].iloc[0] == defaults['height']
    assert result['floors'].iloc[0] == defaults['floors']
    assert result['year'].iloc[0] == defaults['year'] 
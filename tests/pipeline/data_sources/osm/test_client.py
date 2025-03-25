"""
Tests für den OSM-Client.
"""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon, box
from pipeline.data_sources.osm.client import OSMBaseClient

@pytest.fixture
def test_site_gdf():
    """Fixture für ein Test-Site-GeoDataFrame."""
    # Erstelle ein einfaches Polygon für Tests
    polygon = box(16.3, 48.2, 16.4, 48.3)  # Wien-Bereich
    return gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:4326")

@pytest.fixture
def test_config():
    """Fixture für eine Test-Konfiguration."""
    return {
        'buildings': {
            'buffer_distance': 100,
            'defaults': {
                'height': 10,
                'floors': 3
            }
        },
        'streets': {
            'street_types': {
                'primary': {},
                'secondary': {},
                'residential': {}
            },
            'network_type': 'all'
        }
    }

def test_client_initialization(test_config):
    """Test der Client-Initialisierung."""
    client = OSMBaseClient(test_config)
    assert isinstance(client, OSMBaseClient)
    assert hasattr(client, 'config')

def test_fetch_buildings(test_site_gdf, test_config):
    """Test der Gebäudeabfrage."""
    client = OSMBaseClient(test_config)
    buildings = client.fetch_buildings(test_site_gdf)
    
    assert isinstance(buildings, gpd.GeoDataFrame)
    assert not buildings.empty
    assert buildings.crs == test_site_gdf.crs
    assert all(isinstance(geom, Polygon) for geom in buildings.geometry)

def test_fetch_streets(test_site_gdf, test_config):
    """Test der Straßenabfrage."""
    client = OSMBaseClient(test_config)
    streets = client.fetch_streets(test_site_gdf)
    
    assert isinstance(streets, gpd.GeoDataFrame)
    assert not streets.empty
    assert streets.crs == test_site_gdf.crs
    assert 'highway' in streets.columns

def test_empty_site_gdf(test_config):
    """Test mit leerem GeoDataFrame."""
    client = OSMBaseClient(test_config)
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    buildings = client.fetch_buildings(empty_gdf)
    assert isinstance(buildings, gpd.GeoDataFrame)
    assert buildings.empty
    
    streets = client.fetch_streets(empty_gdf)
    assert isinstance(streets, gpd.GeoDataFrame)
    assert streets.empty 
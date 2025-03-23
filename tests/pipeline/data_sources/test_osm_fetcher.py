"""Tests für den OSM Building und Street Fetcher."""

import pytest
import os
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.data_sources.osm_building_fetcher import OSMBuildingFetcher
from pipeline.data_sources.osm_street_fetcher import OSMStreetFetcher
from core.project_paths import get_output_path

def test_fetch_buildings(osm_fetcher, sample_site_gdf):
    """Test der Gebäudeabfrage von OSM."""
    buildings = osm_fetcher.fetch_buildings(sample_site_gdf)
    assert isinstance(buildings, gpd.GeoDataFrame)
    assert len(buildings) > 0
    assert all(buildings.geometry.type == 'Polygon')

def test_fetch_streets(street_fetcher, sample_site_gdf):
    """Test der Straßenabfrage von OSM."""
    streets = street_fetcher.fetch_streets(sample_site_gdf)
    assert isinstance(streets, gpd.GeoDataFrame)
    assert len(streets) > 0
    assert all(streets.geometry.type == 'LineString') 
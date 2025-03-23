import pytest
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from pathlib import Path
import os
from pipeline.geometry.site_polygon import (
    create_site_polygon,
    save_site_polygon
)

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

def test_create_site_polygon(sample_buildings_gdf):
    """Test der create_site_polygon Funktion."""
    # Erstelle Site-Polygon
    site_gdf = create_site_polygon(sample_buildings_gdf, buffer_distance=3)
    
    # Überprüfe, ob ein GeoDataFrame zurückgegeben wurde
    assert isinstance(site_gdf, gpd.GeoDataFrame)
    
    # Überprüfe, ob das CRS korrekt ist
    assert site_gdf.crs == "EPSG:31256"
    
    # Überprüfe, ob die erforderlichen Spalten vorhanden sind
    required_columns = ['Name', 'geometry']
    for col in required_columns:
        assert col in site_gdf.columns
    
    # Überprüfe, ob das Site-Polygon alle Gebäude umschließt
    site_polygon = site_gdf.geometry.iloc[0]
    for building in sample_buildings_gdf.geometry:
        assert site_polygon.contains(building)

def test_save_site_polygon(tmp_path, sample_buildings_gdf):
    """Test der save_site_polygon Funktion."""
    # Erstelle Site-Polygon
    site_gdf = create_site_polygon(sample_buildings_gdf, buffer_distance=3)
    
    # Speichere das Site-Polygon
    output_path = tmp_path / "site.shp"
    save_site_polygon(site_gdf, output_path)
    
    # Überprüfe, ob die Datei existiert
    assert output_path.exists()
    
    # Überprüfe, ob die gespeicherte Datei gelesen werden kann
    saved_gdf = gpd.read_file(output_path)
    assert isinstance(saved_gdf, gpd.GeoDataFrame)
    assert len(saved_gdf) == 1  # Nur ein Site-Polygon
    
    # Überprüfe, ob das CRS korrekt ist
    assert saved_gdf.crs == "EPSG:31256"

def test_create_site_polygon_with_empty_gdf():
    """Test der create_site_polygon Funktion mit leerem GeoDataFrame."""
    # Erstelle leeres GeoDataFrame
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")
    
    # Erstelle Site-Polygon
    site_gdf = create_site_polygon(empty_gdf, buffer_distance=3)
    
    # Überprüfe, ob ein GeoDataFrame zurückgegeben wurde
    assert isinstance(site_gdf, gpd.GeoDataFrame)
    
    # Überprüfe, ob das CRS korrekt ist
    assert site_gdf.crs == "EPSG:31256"
    
    # Überprüfe, ob die erforderlichen Spalten vorhanden sind
    required_columns = ['Name', 'geometry']
    for col in required_columns:
        assert col in site_gdf.columns 
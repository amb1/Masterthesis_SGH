"""Tests für den SitePolygonProcessor."""

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.processing.site_polygon_processor import SitePolygonProcessor

@pytest.fixture
def sample_config():
    return {
        'processing': {
            'site_polygon': {
                'buffer_distance': 3,
                'simplify_tolerance': 0.5
            },
            'file_formats': {
                'shp_driver': 'ESRI Shapefile'
            }
        }
    }

@pytest.fixture
def sample_buildings():
    # Erstelle zwei rechteckige Gebäude
    poly1 = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    poly2 = Polygon([(2, 0), (2, 1), (3, 1), (3, 0)])
    
    return gpd.GeoDataFrame(
        geometry=[poly1, poly2],
        crs='EPSG:31256'
    )

def test_create_site_polygon(sample_config, sample_buildings):
    processor = SitePolygonProcessor(sample_config)
    site_gdf = processor.create_site_polygon(sample_buildings)
    
    assert isinstance(site_gdf, gpd.GeoDataFrame)
    assert len(site_gdf) == 1
    assert site_gdf.crs == sample_buildings.crs
    
    # Prüfe, ob das resultierende Polygon größer ist als die Eingabepolygone
    input_area = sum(sample_buildings.geometry.area)
    output_area = site_gdf.geometry.area.sum()
    assert output_area > input_area

def test_create_site_polygon_empty_input(sample_config):
    processor = SitePolygonProcessor(sample_config)
    empty_gdf = gpd.GeoDataFrame(geometry=[], crs='EPSG:31256')
    
    with pytest.raises(ValueError, match="Keine Gebäude für Site-Polygon-Erstellung vorhanden"):
        processor.create_site_polygon(empty_gdf)

def test_export_site_polygon(sample_config, sample_buildings, tmp_path):
    processor = SitePolygonProcessor(sample_config)
    site_gdf = processor.create_site_polygon(sample_buildings)
    
    output_path = tmp_path / "site.shp"
    processor.export_site_polygon(site_gdf, str(output_path))
    
    assert output_path.exists()
    
    # Prüfe, ob die exportierte Datei wieder eingelesen werden kann
    loaded_gdf = gpd.read_file(str(output_path))
    assert len(loaded_gdf) == len(site_gdf) 
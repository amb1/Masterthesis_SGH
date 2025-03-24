import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.data_sources.wfs_fetcher import ViennaWFS

@pytest.fixture
def sample_config():
    """Test-Konfiguration für Vienna WFS."""
    return {
        'url': 'https://data.wien.gv.at/daten/geo',
        'version': '1.1.0',
        'srsName': 'EPSG:31256',
        'streams': [
            {
                'name': 'Gebäudeinfo',
                'layer': 'ogdwien:GEBAEUDEINFOOGD',
                'priority': 1,
                'fields': ['OBJECTID', 'geometry', 'BAUJAHR'],
                'mapping': {
                    'building_id': 'OBJECTID',
                    'geometry': 'geometry',
                    'construction_year': 'BAUJAHR'
                }
            }
        ],
        'processing': {
            'clip_to_site': True
        }
    }

@pytest.fixture
def sample_site_polygon():
    """Erstellt ein Test-Site-Polygon."""
    polygon = Polygon([
        (16.3, 48.2),  # Ungefähre Koordinaten in Wien
        (16.4, 48.2),
        (16.4, 48.3),
        (16.3, 48.3),
        (16.3, 48.2)
    ])
    return gpd.GeoDataFrame(geometry=[polygon], crs='EPSG:4326')

def test_init(sample_config):
    """Test der Initialisierung."""
    wfs = ViennaWFS(config=sample_config)
    assert wfs.config == sample_config
    assert wfs.wfs_url == sample_config['url']
    assert wfs.version == sample_config['version']

def test_format_bbox(sample_config, sample_site_polygon):
    """Test der BBOX-Formatierung."""
    wfs = ViennaWFS(config=sample_config)
    site_polygon_transformed = sample_site_polygon.to_crs('EPSG:31256')
    bounds = site_polygon_transformed.total_bounds
    bbox = wfs._format_bbox_v11(bounds)
    
    assert isinstance(bbox, str)
    assert 'EPSG:31256' in bbox
    assert len(bbox.split(',')) == 5

def test_fetch_layer(sample_config, sample_site_polygon):
    """Test des Layer-Abrufs."""
    wfs = ViennaWFS(config=sample_config)
    site_polygon_transformed = sample_site_polygon.to_crs('EPSG:31256')
    bounds = site_polygon_transformed.total_bounds
    bbox = wfs._format_bbox_v11(bounds)
    
    layer_name = 'ogdwien:GEBAEUDEINFOOGD'
    gdf = wfs.fetch_layer(layer_name, bbox)
    
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.crs == 'EPSG:31256'
    assert len(gdf) > 0

def test_process_site(sample_config, sample_site_polygon):
    """Test der Site-Verarbeitung."""
    wfs = ViennaWFS(config=sample_config)
    results = wfs.process_site(sample_site_polygon)
    
    assert isinstance(results, dict)
    assert 'Gebäudeinfo' in results
    assert isinstance(results['Gebäudeinfo'], gpd.GeoDataFrame)
    assert results['Gebäudeinfo'].crs == 'EPSG:31256'
    assert len(results['Gebäudeinfo']) > 0

def test_error_handling(sample_config):
    """Test der Fehlerbehandlung."""
    # Test mit ungültiger URL
    bad_config = sample_config.copy()
    bad_config['url'] = 'https://invalid.url'
    
    with pytest.raises(Exception):
        ViennaWFS(config=bad_config)
    
    # Test mit ungültigem Layer
    wfs = ViennaWFS(config=sample_config)
    with pytest.raises(Exception):
        wfs.fetch_layer('invalid:layer', '0,0,1,1,EPSG:31256') 
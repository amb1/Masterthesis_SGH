import pytest
import geopandas as gpd
from shapely.geometry import Polygon, LineString, MultiPolygon
from pathlib import Path
import os
from unittest.mock import patch, MagicMock
from pipeline.data_sources.osm_street_fetcher import (
    fetch_streets_within_site,
    process_streets,
    save_streets,
    fetch_osm_streets,
    load_osm_config,
    main
)
import tempfile
from osmnx._errors import InsufficientResponseError

@pytest.fixture
def sample_site_gdf():
    """Erstellt ein Beispiel-Site-Polygon für Tests."""
    # Erstelle ein einfaches Polygon
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    return gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")

@pytest.fixture
def sample_config():
    """Erstellt eine Beispiel-Konfiguration für Tests."""
    return {
        'tags': {
            'highway': ['primary', 'secondary', 'tertiary', 'residential']
        },
        'defaults': {
            'width': 5,
            'lanes': 2,
            'surface': 'asphalt',
            'REFERENCE': ''
        }
    }

@pytest.fixture
def mock_osm_data():
    """Erstellt Mock-OSM-Daten für Tests"""
    # Erstelle zwei Beispiel-Straßen
    street1 = LineString([(0, 0), (100, 0)])
    street2 = LineString([(0, 50), (100, 50)])
    
    # Erstelle GeoDataFrame mit den Straßen
    streets_gdf = gpd.GeoDataFrame(
        {
            'name': ['Hauptstraße', 'Nebenstraße'],
            'width': [6, 4],
            'lanes': [2, 1],
            'surface': ['asphalt', 'concrete'],
            'highway': ['primary', 'secondary'],
            'ref': ['B1', 'L123'],
            'geometry': [street1, street2]
        },
        crs="EPSG:31256"
    )
    return streets_gdf

@pytest.fixture
def mock_osmnx_graph():
    """Erstellt einen Mock-OSMnx-Graphen für Tests"""
    # Erstelle zwei Beispiel-Straßen
    street1 = LineString([(0, 0), (100, 0)])
    street2 = LineString([(0, 50), (100, 50)])
    
    # Erstelle GeoDataFrame mit den Straßen
    edges_gdf = gpd.GeoDataFrame(
        {
            'name': ['Hauptstraße', 'Nebenstraße'],
            'width': [6, 4],
            'lanes': [2, 1],
            'surface': ['asphalt', 'concrete'],
            'highway': ['primary', 'secondary'],
            'ref': ['B1', 'L123'],
            'geometry': [street1, street2]
        },
        crs="EPSG:31256"
    )
    
    # Erstelle einen Mock-Graphen
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=edges_gdf)
    return mock_graph

def test_fetch_streets_within_site(sample_site_gdf, sample_config, mock_osmnx_graph):
    """Test der fetch_streets_within_site Funktion"""
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_osmnx_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_osmnx_graph.edges()):
        
        result = fetch_streets_within_site(sample_site_gdf, sample_config)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.crs == sample_site_gdf.crs
        assert len(result) == 2
        assert all(col in result.columns for col in ['Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'])

def test_process_streets(mock_osm_data):
    """Test der process_streets Funktion"""
    defaults = {
        'width': 5,
        'lanes': 2,
        'surface': 'asphalt',
        'REFERENCE': ''
    }
    
    result = process_streets(mock_osm_data, defaults)
    
    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs == mock_osm_data.crs
    assert len(result) == 2
    assert all(col in result.columns for col in ['Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'])
    assert result['Name'].iloc[0] == 'Hauptstraße'
    assert result['REFERENCE'].iloc[0] == 'B1'

def test_save_streets(mock_osm_data):
    """Test der save_streets Funktion"""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / 'streets.shp'
        save_streets(mock_osm_data, output_path)
        
        assert output_path.exists()
        saved_gdf = gpd.read_file(output_path)
        assert isinstance(saved_gdf, gpd.GeoDataFrame)
        assert len(saved_gdf) == len(mock_osm_data)

def test_fetch_osm_streets(sample_site_gdf, sample_config, mock_osmnx_graph):
    """Test der fetch_osm_streets Funktion"""
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_osmnx_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_osmnx_graph.edges()):
        
        result = fetch_osm_streets(sample_site_gdf, sample_config)
        
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.crs == sample_site_gdf.crs
        assert len(result) == 2
        assert all(col in result.columns for col in ['Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'])

def test_load_osm_config_missing_file():
    """Test der Fehlerbehandlung wenn die Konfigurationsdatei fehlt"""
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=None):
        config = load_osm_config()
        assert config is None

def test_load_osm_config_invalid_structure():
    """Test der Fehlerbehandlung bei ungültiger Konfigurationsstruktur"""
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value={'invalid': 'structure'}):
        config = load_osm_config()
        assert config is None

def test_load_osm_config_missing_streets():
    """Test der Fehlerbehandlung wenn die Straßen-Konfiguration fehlt"""
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value={'osm': {}}):
        config = load_osm_config()
        assert config is None

def test_load_osm_config_valid():
    """Test des erfolgreichen Ladens einer gültigen Konfiguration"""
    valid_config = {
        'osm': {
            'streets': {
                'tags': {
                    'highway': ['primary', 'secondary']
                },
                'defaults': {
                    'width': 5,
                    'lanes': 2
                }
            }
        }
    }
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=valid_config):
        config = load_osm_config()
        assert config is not None
        assert 'tags' in config
        assert 'defaults' in config
        assert config['tags']['highway'] == ['primary', 'secondary']
        assert config['defaults']['width'] == 5
        assert config['defaults']['lanes'] == 2

def test_fetch_streets_within_site_no_crs():
    """Test der Fehlerbehandlung wenn kein CRS vorhanden ist"""
    from pipeline.data_sources.osm_street_fetcher import fetch_streets_within_site
    
    # Erstelle ein GeoDataFrame ohne CRS
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[polygon])
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Erstelle ein Mock-GeoDataFrame mit Geometrie
    mock_edges = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326"  # WGS84
    )
    
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges):
        
        result = fetch_streets_within_site(site_gdf, config)
        assert result.crs == "EPSG:31256"  # Prüfe ob CRS gesetzt wurde

def test_fetch_streets_within_site_no_streets():
    """Test der Fehlerbehandlung wenn keine Straßen gefunden werden"""
    from pipeline.data_sources.osm_street_fetcher import fetch_streets_within_site
    
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Erstelle ein leeres GeoDataFrame mit korrekter Struktur
    mock_edges = gpd.GeoDataFrame(
        columns=['name', 'width', 'lanes', 'surface', 'highway', 'ref', 'geometry'],
        crs="EPSG:31256"
    )
    
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges):
        
        result = fetch_streets_within_site(site_gdf, config)
        assert isinstance(result, gpd.GeoDataFrame)
        assert len(result) == 0
        assert result.crs == site_gdf.crs

def test_fetch_streets_within_site_invalid_input():
    """Test der Fehlerbehandlung bei ungültiger Eingabe"""
    from pipeline.data_sources.osm_street_fetcher import fetch_streets_within_site
    
    # Erstelle ein GeoDataFrame mit einer ungültigen Geometrie
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame({'dummy': [1], 'geometry': [polygon]}, crs="EPSG:31256")
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    with pytest.raises((AttributeError, IndexError, InsufficientResponseError)):  # Akzeptiere alle erwarteten Fehlertypen
        fetch_streets_within_site(site_gdf, config)

def test_main():
    """Test der Hauptfunktion"""
    from pipeline.data_sources.osm_street_fetcher import main
    
    # Mock-Konfigurationen
    osm_config = {
        'tags': {'highway': ['primary', 'secondary']},
        'defaults': {'width': 5, 'lanes': 2}
    }
    
    global_config = {
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_osm_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=global_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.save_streets'):
        
        # Führe die Hauptfunktion aus
        main()

def test_fetch_osm_streets_invalid_config():
    """Test der fetch_osm_streets Funktion mit ungültiger Konfiguration"""
    from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
    
    # Erstelle ein gültiges GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    # Test mit ungültiger Konfiguration
    invalid_config = "keine gültige config"
    
    result = fetch_osm_streets(site_gdf, invalid_config)
    assert isinstance(result, gpd.GeoDataFrame)
    assert result.crs == site_gdf.crs
    assert len(result) == 0

def test_fetch_osm_streets_network_error():
    """Test der fetch_osm_streets Funktion bei Netzwerkfehlern"""
    from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
    
    # Erstelle ein gültiges GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Simuliere einen Netzwerkfehler
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', 
              side_effect=InsufficientResponseError("Keine Daten gefunden")):
        result = fetch_osm_streets(site_gdf, config)
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.crs == "EPSG:31256"
        assert len(result) == 0
        assert all(col in result.columns for col in ['Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'])

def test_main_missing_global_config():
    """Test der main()-Funktion bei fehlender globaler Konfiguration"""
    from pipeline.data_sources.osm_street_fetcher import main
    
    # Mock-Konfigurationen
    osm_config = {
        'tags': {'highway': ['primary', 'secondary']},
        'defaults': {'width': 5, 'lanes': 2}
    }
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_osm_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=None), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True):
        
        with pytest.raises(ValueError, match="❌ Keine gültige globale Konfiguration gefunden"):
            main()

def test_main_missing_output_paths():
    """Test der main()-Funktion bei fehlenden Ausgabepfaden"""
    from pipeline.data_sources.osm_street_fetcher import main
    
    # Mock-Konfigurationen
    osm_config = {
        'tags': {'highway': ['primary', 'secondary']},
        'defaults': {'width': 5, 'lanes': 2}
    }
    
    global_config = {
        'paths': {}  # Leere Pfade
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_osm_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=global_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.save_streets'):
        
        # Die Funktion sollte trotz fehlender Pfade durchlaufen
        main()

def test_main_empty_streets():
    """Test der main()-Funktion bei leeren Straßen"""
    from pipeline.data_sources.osm_street_fetcher import main
    
    # Mock-Konfigurationen
    osm_config = {
        'tags': {'highway': ['primary', 'secondary']},
        'defaults': {'width': 5, 'lanes': 2}
    }
    
    global_config = {
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    # Leeres GeoDataFrame für Straßen
    empty_streets = gpd.GeoDataFrame()
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_osm_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=global_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', return_value=empty_streets):
        
        # Die Funktion sollte bei leeren Straßen ohne Fehler beendet werden
        main()

def test_main_no_crs():
    """Test der main()-Funktion bei fehlendem CRS in site.shp"""
    from pipeline.data_sources.osm_street_fetcher import main
    
    # Mock-Konfigurationen
    osm_config = {
        'tags': {'highway': ['primary', 'secondary']},
        'defaults': {'width': 5, 'lanes': 2}
    }
    
    global_config = {
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame ohne CRS
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon])
    
    # Mock site.shp GeoDataFrame mit CRS nach der Konvertierung
    mock_site_with_crs = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_osm_config', return_value=osm_config), \
         patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=global_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', return_value=mock_site_with_crs), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', return_value=mock_site_with_crs), \
         patch('pipeline.data_sources.osm_street_fetcher.save_streets'):
        
        # Die Funktion sollte das CRS korrekt setzen und durchlaufen
        main()

def test_fetch_osm_streets_multipolygon():
    """Test der fetch_osm_streets Funktion mit MultiPolygon-Eingabe"""
    from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
    from shapely.geometry import MultiPolygon, Polygon
    
    # Erstelle ein MultiPolygon
    polygon1 = Polygon([(0, 0), (0, 50), (50, 50), (50, 0), (0, 0)])
    polygon2 = Polygon([(50, 50), (50, 100), (100, 100), (100, 50), (50, 50)])
    multipolygon = MultiPolygon([polygon1, polygon2])
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Mock OSM-Daten
    mock_edges = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326"  # WGS84
    )
    
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges):
        
        result = fetch_osm_streets(multipolygon, config)
        assert isinstance(result, gpd.GeoDataFrame)
        assert result.crs == "EPSG:31256"

def test_fetch_osm_streets_intersection_filter():
    """Test der fetch_osm_streets Funktion mit Straßenfilterung"""
    from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
    
    # Erstelle ein Site-Polygon
    site_polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[site_polygon], crs="EPSG:31256")
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Erstelle Mock-Straßen, von denen nur eine das Site-Polygon schneidet
    street1 = LineString([(50, 50), (150, 50)])  # Schneidet
    street2 = LineString([(150, 150), (200, 150)])  # Schneidet nicht
    
    mock_edges = gpd.GeoDataFrame(
        {
            'geometry': [street1, street2],
            'highway': ['primary', 'secondary']
        },
        crs="EPSG:31256"
    )
    
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges):
        
        result = fetch_osm_streets(site_gdf, config)
        assert len(result) == 1
        assert result.geometry.iloc[0].equals(street1)

def test_fetch_osm_streets_crs_conversion():
    """Test der fetch_osm_streets Funktion mit CRS-Konvertierung"""
    from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
    
    # Erstelle ein Site-Polygon in WGS84
    site_polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    site_gdf = gpd.GeoDataFrame(geometry=[site_polygon], crs="EPSG:4326")
    
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Mock OSM-Daten in WGS84
    mock_edges = gpd.GeoDataFrame(
        {
            'name': ['Teststraße'],
            'width': [5],
            'lanes': [2],
            'surface': ['asphalt'],
            'highway': ['primary'],
            'geometry': [LineString([(0, 0), (1, 1)])]
        },
        crs="EPSG:4326"  # WGS84
    )
    
    mock_graph = MagicMock()
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', return_value=mock_edges.to_crs("EPSG:31256")):
        
        result = fetch_osm_streets(site_gdf, config)
        assert result.crs == "EPSG:31256"  # Sollte in MGI/Austria Lambert konvertiert werden 

def create_mock_site():
    """Erstellt ein Mock-Site-GeoDataFrame für Tests"""
    from shapely.geometry import Polygon
    import geopandas as gpd
    
    # Erstelle ein einfaches Polygon
    polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
    return gpd.GeoDataFrame({'geometry': [polygon]}, crs="EPSG:4326")

def test_load_osm_config_file_error():
    """Test für Fehler beim Lesen der Konfigurationsdatei"""
    with patch('builtins.open', side_effect=IOError("Datei nicht lesbar")):
        config = load_osm_config()
        assert config is None

def test_fetch_streets_within_site_processing_error():
    """Test für Fehler bei der Verarbeitung der Straßen"""
    mock_site = create_mock_site()
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Mock für graph_from_polygon
    mock_graph = MagicMock()
    mock_edges = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326"
    )
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', side_effect=Exception("Verarbeitungsfehler")):
        with pytest.raises(Exception) as exc_info:
            fetch_streets_within_site(mock_site, config)
        assert str(exc_info.value) == "Verarbeitungsfehler"

def test_fetch_osm_streets_processing_error():
    """Test für Fehler bei der Verarbeitung der OSM-Straßen"""
    mock_site = create_mock_site()
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Mock für graph_from_polygon
    mock_graph = MagicMock()
    mock_edges = gpd.GeoDataFrame(
        geometry=[LineString([(0, 0), (1, 1)])],
        crs="EPSG:4326"
    )
    mock_graph.edges = MagicMock(return_value=mock_edges)
    
    with patch('pipeline.data_sources.osm_street_fetcher.ox.graph_from_polygon', return_value=mock_graph), \
         patch('pipeline.data_sources.osm_street_fetcher.ox.graph_to_gdfs', return_value=mock_edges), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', side_effect=Exception("Verarbeitungsfehler")):
        with pytest.raises(Exception) as exc_info:
            fetch_osm_streets(mock_site, config)
        assert str(exc_info.value) == "Verarbeitungsfehler"

def test_main_processing_error():
    """Test für Fehler bei der Verarbeitung in main()"""
    mock_config = {
        'osm': {
            'streets': {
                'tags': {
                    'highway': ['primary', 'secondary']
                }
            }
        },
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=mock_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', side_effect=Exception("Verarbeitungsfehler")):
        with pytest.raises(Exception) as exc_info:
            main()
        assert str(exc_info.value) == "Verarbeitungsfehler"

def test_main_save_error():
    """Test für Fehler beim Speichern der Daten"""
    mock_config = {
        'osm': {
            'streets': {
                'tags': {
                    'highway': ['primary', 'secondary']
                }
            }
        },
        'paths': {
            'outputs': {
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        }
    }
    
    # Mock site.shp GeoDataFrame
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    mock_site = gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.load_yaml_config', return_value=mock_config), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.mkdir'), \
         patch('pipeline.data_sources.osm_street_fetcher.Path.exists', return_value=True), \
         patch('pipeline.data_sources.osm_street_fetcher.gpd.read_file', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.fetch_osm_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.process_streets', return_value=mock_site), \
         patch('pipeline.data_sources.osm_street_fetcher.save_streets', side_effect=IOError("Speicherfehler")):
        with pytest.raises(IOError) as exc_info:
            main()
        assert str(exc_info.value) == "Speicherfehler"

def test_fetch_osm_streets_empty_response():
    """Test für leere OSM-Antwort"""
    mock_site = create_mock_site()
    config = {
        'tags': {
            'highway': ['primary', 'secondary']
        }
    }
    
    # Mock für leere Antwort
    empty_gdf = gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:31256")
    
    with patch('pipeline.data_sources.osm_street_fetcher.fetch_streets_within_site', return_value=empty_gdf):
        result = fetch_osm_streets(mock_site, config)
        assert len(result) == 0
        assert result.crs == "EPSG:31256" 
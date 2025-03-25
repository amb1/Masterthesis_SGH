"""
Tests für den WFS-Fetcher.
"""

import pytest
import geopandas as gpd
from unittest.mock import Mock, patch
from shapely.geometry import Polygon
import pandas as pd

from pipeline.data_sources.wfs_fetcher import ViennaWFSFetcher, fetch_wfs_buildings

# Test-Konfiguration
TEST_CONFIG = {
    "url": "https://test.wfs.wien.at/wfs",
    "version": "1.1.0",
    "timeout": 30,
    "srsName": "EPSG:31256",
    "streams": [
        {
            "name": "buildings",
            "layer": "ogdwien:GEBAEUDEPKT",
            "filters": {}
        }
    ]
}

# Test-Daten
@pytest.fixture
def test_gdf():
    """Erstellt ein Test-GeoDataFrame."""
    geometry = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]
    data = {
        'id': [1],
        'name': ['Test Building'],
        'geometry': geometry
    }
    return gpd.GeoDataFrame(data, geometry='geometry', crs="EPSG:31256")

@pytest.fixture
def mock_wfs_response(test_gdf):
    """Erstellt eine Mock-Response für WFS-Anfragen."""
    return {
        'buildings': test_gdf
    }

@pytest.fixture
def mock_wfs_client():
    """Erstellt einen Mock WFS Client."""
    with patch('pipeline.data_sources.wfs.client.WebFeatureService') as mock_wfs:
        yield mock_wfs

class TestViennaWFSFetcher:
    """Tests für die ViennaWFSFetcher-Klasse."""
    
    def test_init(self, mock_wfs_client):
        """Test der Initialisierung."""
        fetcher = ViennaWFSFetcher(config=TEST_CONFIG)
        assert fetcher.config.url == TEST_CONFIG["url"]
        assert fetcher.config.version == TEST_CONFIG["version"]
        assert fetcher.config.timeout == TEST_CONFIG["timeout"]
        assert fetcher.config.srs_name == TEST_CONFIG["srsName"]
        
    @patch('pipeline.data_sources.wfs.WFSStreamHandler.process_streams')
    def test_fetch_buildings(self, mock_process_streams, mock_wfs_response, mock_wfs_client):
        """Test des Gebäude-Abrufs."""
        # Mock konfigurieren
        mock_process_streams.return_value = mock_wfs_response
        
        # Fetcher initialisieren und Methode aufrufen
        fetcher = ViennaWFSFetcher(config=TEST_CONFIG)
        result = fetcher.fetch_buildings()
        
        # Überprüfungen
        assert isinstance(result, dict)
        assert 'buildings' in result
        assert isinstance(result['buildings'], gpd.GeoDataFrame)
        mock_process_streams.assert_called_once_with(None)
        
    @patch('pipeline.data_sources.wfs.WFSStreamHandler.process_streams')
    def test_fetch_buildings_with_bbox(self, mock_process_streams, mock_wfs_response, mock_wfs_client):
        """Test des Gebäude-Abrufs mit BBOX."""
        # Mock konfigurieren
        mock_process_streams.return_value = mock_wfs_response
        test_bbox = "1234,5678,9012,3456"
        
        # Fetcher initialisieren und Methode aufrufen
        fetcher = ViennaWFSFetcher(config=TEST_CONFIG)
        result = fetcher.fetch_buildings(bbox=test_bbox)
        
        # Überprüfungen
        assert isinstance(result, dict)
        mock_process_streams.assert_called_once_with(test_bbox)
        
    def test_fetch_buildings_error_handling(self, mock_wfs_client):
        """Test der Fehlerbehandlung beim Gebäude-Abruf."""
        # Fetcher mit ungültiger Konfiguration
        invalid_config = {}
        fetcher = ViennaWFSFetcher(config=invalid_config)
        result = fetcher.fetch_buildings()
        
        # Überprüfungen
        assert isinstance(result, dict)
        assert len(result) == 0
        
    @patch('pipeline.data_sources.wfs.WFSGeometryProcessor.create_bbox_from_gdf')
    @patch('pipeline.data_sources.wfs.WFSStreamHandler.process_streams')
    def test_fetch_building_model(self, mock_process_streams, mock_create_bbox, 
                                mock_wfs_response, test_gdf, mock_wfs_client):
        """Test des Gebäudemodell-Abrufs."""
        # Mocks konfigurieren
        test_bbox = "1234,5678,9012,3456"
        mock_create_bbox.return_value = test_bbox
        mock_process_streams.return_value = mock_wfs_response
        
        # Fetcher initialisieren und Methode aufrufen
        fetcher = ViennaWFSFetcher(config=TEST_CONFIG)
        result = fetcher.fetch_building_model(test_gdf)
        
        # Überprüfungen
        assert isinstance(result, dict)
        mock_create_bbox.assert_called_once_with(test_gdf)
        mock_process_streams.assert_called_once_with(test_bbox)
        
    def test_fetch_building_model_error_handling(self, test_gdf, mock_wfs_client):
        """Test der Fehlerbehandlung beim Gebäudemodell-Abruf."""
        # Fetcher mit ungültiger Konfiguration
        invalid_config = {}
        fetcher = ViennaWFSFetcher(config=invalid_config)
        result = fetcher.fetch_building_model(test_gdf)
        
        # Überprüfungen
        assert isinstance(result, dict)
        assert len(result) == 0

def test_fetch_wfs_buildings_success(mock_wfs_response, mock_wfs_client):
    """Test der erfolgreichen Ausführung von fetch_wfs_buildings."""
    with patch('pipeline.data_sources.wfs_fetcher.ViennaWFSFetcher') as mock_fetcher_class:
        # Mock Fetcher konfigurieren
        mock_fetcher = Mock()
        mock_fetcher.fetch_buildings.return_value = mock_wfs_response
        mock_fetcher_class.return_value = mock_fetcher
        
        # Funktion aufrufen
        result = fetch_wfs_buildings(TEST_CONFIG)
        
        # Überprüfungen
        assert isinstance(result, dict)
        assert result == mock_wfs_response
        mock_fetcher_class.assert_called_once_with(config=TEST_CONFIG)
        mock_fetcher.fetch_buildings.assert_called_once()

def test_fetch_wfs_buildings_error(mock_wfs_client):
    """Test der Fehlerbehandlung von fetch_wfs_buildings."""
    with patch('pipeline.data_sources.wfs_fetcher.ViennaWFSFetcher') as mock_fetcher_class:
        # Mock Fetcher konfigurieren um Fehler zu werfen
        mock_fetcher = Mock()
        mock_fetcher.fetch_buildings.side_effect = Exception("Test Error")
        mock_fetcher_class.return_value = mock_fetcher
        
        # Funktion aufrufen
        result = fetch_wfs_buildings(TEST_CONFIG)
        
        # Überprüfungen
        assert isinstance(result, dict)
        assert len(result) == 0
        mock_fetcher_class.assert_called_once_with(config=TEST_CONFIG)
        mock_fetcher.fetch_buildings.assert_called_once() 
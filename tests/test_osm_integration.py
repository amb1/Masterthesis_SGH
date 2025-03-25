"""
Tests für die OSM-Integration.
"""

import unittest
from unittest.mock import Mock, patch
import geopandas as gpd
from shapely.geometry import Polygon, Point, MultiPolygon
import pandas as pd
from pipeline.data_sources.osm.client import OSMClient
from pipeline.data_sources.osm.geometry import OSMGeometry
from pipeline.data_sources.osm.stream import OSMStream

class TestOSMIntegration(unittest.TestCase):
    
    def setUp(self):
        """Test-Setup mit Mock-Daten"""
        # Test-Polygon
        self.test_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
        
        # Mock OSM-Gebäude
        self.test_buildings = {
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Polygon',
                        'coordinates': [[(0.1, 0.1), (0.1, 0.2), (0.2, 0.2), (0.2, 0.1), (0.1, 0.1)]]
                    },
                    'properties': {
                        'building': 'residential',
                        'height': '10',
                        'levels': '3',
                        'name': 'Testgebäude'
                    }
                }
            ]
        }
        
        # Mock OSM-Straßen
        self.test_streets = {
            'features': [
                {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [(0.1, 0.1), (0.9, 0.9)]
                    },
                    'properties': {
                        'highway': 'residential',
                        'name': 'Teststraße',
                        'lanes': '2',
                        'surface': 'asphalt'
                    }
                }
            ]
        }
        
    @patch('osmnx.features_from_polygon')
    def test_get_buildings(self, mock_features):
        """Test: Gebäude von OSM abrufen"""
        # Mock konfigurieren
        mock_gdf = gpd.GeoDataFrame.from_features(self.test_buildings['features'])
        mock_gdf.crs = 'EPSG:4326'  # WGS84
        mock_features.return_value = mock_gdf
        
        # Client initialisieren und Gebäude abrufen
        client = OSMClient()
        result = client.get_buildings(self.test_polygon)
        
        # Prüfungen
        self.assertIsNotNone(result)
        self.assertIn('features', result)
        self.assertEqual(len(result['features']), 1)
        self.assertEqual(result['features'][0]['properties']['name'], 'Testgebäude')
        
    @patch('osmnx.features_from_polygon')
    def test_get_streets(self, mock_features):
        """Test: Straßen von OSM abrufen"""
        # Mock konfigurieren
        mock_gdf = gpd.GeoDataFrame.from_features(self.test_streets['features'])
        mock_gdf.crs = 'EPSG:4326'  # WGS84
        mock_features.return_value = mock_gdf
        
        # Client initialisieren und Straßen abrufen
        client = OSMClient()
        result = client.get_streets(self.test_polygon)
        
        # Prüfungen
        self.assertIsNotNone(result)
        self.assertIn('features', result)
        self.assertEqual(len(result['features']), 1)
        self.assertEqual(result['features'][0]['properties']['name'], 'Teststraße')
        
    def test_get_feature_info(self):
        """Test: Feature-Informationen abrufen"""
        client = OSMClient()
        
        # Test: Gebäude-Info
        buildings_info = client.get_feature_info('buildings')
        self.assertEqual(buildings_info['name'], 'buildings')
        self.assertIn('height', buildings_info['properties'])
        self.assertIn('levels', buildings_info['properties'])
        
        # Test: Straßen-Info
        streets_info = client.get_feature_info('streets')
        self.assertEqual(streets_info['name'], 'streets')
        self.assertIn('highway', streets_info['properties'])
        self.assertIn('lanes', streets_info['properties'])
        
        # Test: Ungültiger Typ
        invalid_info = client.get_feature_info('invalid')
        self.assertEqual(invalid_info, {})
        
    def test_geometry_processing(self):
        """Test: Geometrie-Verarbeitung"""
        geometry = OSMGeometry()
        
        # Test: Validierung
        valid_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
        self.assertTrue(geometry.validate_geometry(valid_polygon))
        
        # Test: Vereinfachung
        complex_polygon = Polygon([
            (0, 0), (0.1, 0.1), (0.2, 0.2), (0.3, 0.3),
            (1, 1), (1, 0), (0.7, 0), (0.5, 0), (0, 0)
        ])
        simplified = geometry.simplify_geometry(complex_polygon)
        self.assertLess(len(simplified.exterior.coords), len(complex_polygon.exterior.coords))
        
        # Test: Grundriss-Extraktion
        multi_polygon = MultiPolygon([
            Polygon([(0, 0), (0, 1), (1, 1), (1, 0)]),
            Polygon([(2, 2), (2, 3), (3, 3), (3, 2)])
        ])
        footprint = geometry.extract_footprint(multi_polygon)
        self.assertIsInstance(footprint, Polygon)
        
    @patch('osmnx.features_from_polygon')
    def test_stream_processing(self, mock_features):
        """Test: Stream-Verarbeitung"""
        # Mock konfigurieren
        mock_gdf = gpd.GeoDataFrame.from_features(self.test_buildings['features'])
        mock_gdf.crs = 'EPSG:4326'  # WGS84
        mock_features.return_value = mock_gdf
        
        stream = OSMStream(chunk_size=2)
        
        # Test: Feature-Streaming
        chunks = list(stream.stream_features(self.test_polygon, {'building': True}))
        
        # Prüfungen
        self.assertIsInstance(chunks, list)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['properties']['name'], 'Testgebäude')
        
if __name__ == '__main__':
    unittest.main() 
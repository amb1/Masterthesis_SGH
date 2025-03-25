import unittest
from unittest.mock import Mock, patch
import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from pipeline.data_sources.wfs.client import WFSClient
from pipeline.processing.cea_mapper import CEAMapper, enrich_building_data

class TestWFSIntegration(unittest.TestCase):
    
    def setUp(self):
        """Test-Setup mit Mock-Daten"""
        # Mock GeoDataFrame erstellen
        geometry = [Point(1, 1), Point(2, 2)]
        self.test_gdf = gpd.GeoDataFrame({
            'geometry': geometry,
            'id': ['1', '2']
        })
        
        # Mock WFS-Daten
        self.test_wfs_data = {
            'Gebäudeinfo': {
                'features': [
                    {
                        'properties': {
                            'STRNAML': 'Teststraße',
                            'VONN': '1',
                            'BAUJAHR': '1960',
                            'L_NUTZUNG': 'Wohngebäude'
                        }
                    },
                    {
                        'properties': {
                            'STRNAML': 'Musterweg',
                            'VONN': '2',
                            'BAUJAHR': '1980',
                            'L_NUTZUNG': 'Bürogebäude'
                        }
                    }
                ]
            }
        }
        
    @patch('pipeline.data_sources.wfs.client.WFSClient')
    def test_wfs_data_enrichment(self, mock_wfs_client):
        """Test: WFS-Daten werden korrekt mit Gebäudedaten verknüpft"""
        # Mock WFS-Client konfigurieren
        mock_client = Mock()
        mock_client.get_features.return_value = self.test_wfs_data
        mock_wfs_client.return_value = mock_client
        
        # Daten anreichern
        enriched_gdf = enrich_building_data(self.test_gdf, self.test_wfs_data)
        
        # Prüfen ob die Felder korrekt hinzugefügt wurden
        self.assertIn('Gebäudeinfo_STRNAML', enriched_gdf.columns)
        self.assertIn('Gebäudeinfo_VONN', enriched_gdf.columns)
        self.assertIn('Gebäudeinfo_BAUJAHR', enriched_gdf.columns)
        self.assertIn('Gebäudeinfo_L_NUTZUNG', enriched_gdf.columns)
        
        # Prüfen ob die Werte korrekt gemappt wurden
        self.assertEqual(enriched_gdf.at[0, 'Gebäudeinfo_STRNAML'], 'Teststraße')
        self.assertEqual(enriched_gdf.at[1, 'Gebäudeinfo_STRNAML'], 'Musterweg')
        
    def test_wfs_data_validation(self):
        """Test: WFS-Daten werden vor der Verarbeitung validiert"""
        # Test mit leeren WFS-Daten
        empty_wfs_data = {}
        enriched_gdf = enrich_building_data(self.test_gdf, empty_wfs_data)
        self.assertEqual(len(enriched_gdf.columns), len(self.test_gdf.columns))
        
        # Test mit ungültigen WFS-Daten
        invalid_wfs_data = {'Gebäudeinfo': {}}
        enriched_gdf = enrich_building_data(self.test_gdf, invalid_wfs_data)
        self.assertEqual(len(enriched_gdf.columns), len(self.test_gdf.columns))
        
    def test_wfs_field_mapping(self):
        """Test: WFS-Felder werden korrekt auf CEA-Attribute gemappt"""
        enriched_gdf = enrich_building_data(self.test_gdf, self.test_wfs_data)
        
        # CEA-Mapper mit Test-Konfiguration initialisieren
        config = {
            'cea_mappings': {
                'zone': {
                    'Name': {
                        'sources': {
                            'wfs': {
                                'street': 'Gebäudeinfo_STRNAML',
                                'number': 'Gebäudeinfo_VONN'
                            },
                            'format': '{street}_{number}'
                        }
                    }
                }
            }
        }
        
        mapper = CEAMapper(config)
        
        # Zone-Datei erstellen
        zone_gdf = mapper.create_zone_file(enriched_gdf)
        
        # Prüfen ob die Namen korrekt generiert wurden
        self.assertEqual(zone_gdf.at[0, 'Name'], 'Teststraße_1')
        self.assertEqual(zone_gdf.at[1, 'Name'], 'Musterweg_2')
        
    def test_wfs_error_handling(self):
        """Test: Fehler bei der WFS-Verarbeitung werden korrekt behandelt"""
        # Test mit fehlenden Features
        invalid_wfs_data = {
            'Gebäudeinfo': {
                'features': None
            }
        }
        enriched_gdf = enrich_building_data(self.test_gdf, invalid_wfs_data)
        self.assertEqual(len(enriched_gdf), len(self.test_gdf))
        
        # Test mit ungültigen Properties
        invalid_wfs_data = {
            'Gebäudeinfo': {
                'features': [
                    {'properties': None},
                    {'properties': None}
                ]
            }
        }
        enriched_gdf = enrich_building_data(self.test_gdf, invalid_wfs_data)
        self.assertEqual(len(enriched_gdf), len(self.test_gdf))

if __name__ == '__main__':
    unittest.main() 
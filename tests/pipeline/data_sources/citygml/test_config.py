"""
Tests für die CityGML-Konfigurationsklasse.
"""

import unittest
from pathlib import Path
from pipeline.data_sources.citygml.config import CityGMLConfig, CityGMLConfigError

class TestCityGMLConfig(unittest.TestCase):
    """Testklasse für CityGML-Konfiguration."""
    
    def setUp(self):
        """Test-Setup."""
        self.valid_config = {
            'namespaces': {
                'gml': 'http://www.opengis.net/gml',
                'bldg': 'http://www.opengis.net/citygml/building/2.0'
            },
            'required_fields': ['measured_height', 'year_of_construction'],
            'geometry': {
                'srs_name': 'EPSG:31256',
                'validation': {
                    'min_area': 10.0,
                    'max_angle': 80
                }
            },
            'citygml_fields': {
                'measured_height': {
                    'type': 'float',
                    'xpath': './/bldg:measuredHeight',
                    'fallback': 10.0
                }
            }
        }
        
    def test_init_with_dict(self):
        """Test Initialisierung mit Dictionary."""
        config = CityGMLConfig(config=self.valid_config)
        self.assertEqual(config.namespaces, self.valid_config['namespaces'])
        self.assertEqual(config.required_fields, self.valid_config['required_fields'])
        
    def test_init_empty(self):
        """Test Initialisierung ohne Konfiguration."""
        config = CityGMLConfig()
        self.assertEqual(config.config, {})
        
    def test_validate_valid_config(self):
        """Test Validierung mit gültiger Konfiguration."""
        config = CityGMLConfig(config=self.valid_config)
        self.assertTrue(config.validate())
        
    def test_validate_missing_sections(self):
        """Test Validierung mit fehlenden Pflichtfeldern."""
        invalid_config = {
            'namespaces': self.valid_config['namespaces']
        }
        config = CityGMLConfig(config=invalid_config)
        self.assertFalse(config.validate())
        
    def test_validate_invalid_namespaces(self):
        """Test Validierung mit ungültigen Namespaces."""
        invalid_config = self.valid_config.copy()
        invalid_config['namespaces'] = 'invalid'
        config = CityGMLConfig(config=invalid_config)
        self.assertFalse(config.validate())
        
    def test_properties(self):
        """Test Zugriff auf Eigenschaften."""
        config = CityGMLConfig(config=self.valid_config)
        self.assertEqual(config.namespaces, self.valid_config['namespaces'])
        self.assertEqual(config.required_fields, self.valid_config['required_fields'])
        self.assertEqual(config.geometry_config, self.valid_config['geometry'])
        self.assertEqual(config.field_config, self.valid_config['citygml_fields'])
        self.assertFalse(config.debug_enabled)
        self.assertEqual(config.output_formats, [])
        
if __name__ == '__main__':
    unittest.main() 
"""
Tests für den CityGML-Attribut-Prozessor.
"""

import unittest
from lxml import etree
from pipeline.data_sources.citygml.attributes import CityGMLAttributeProcessor

class TestCityGMLAttributeProcessor(unittest.TestCase):
    """Testklasse für CityGML-Attribut-Prozessor."""
    
    def setUp(self):
        """Test-Setup."""
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/2.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0'
        }
        
        self.config = {
            'required_fields': ['measured_height', 'building_type'],
            'citygml_fields': {
                'measured_height': {
                    'type': 'float',
                    'xpath': './/bldg:measuredHeight',
                    'fallback': 10.0
                },
                'building_type': {
                    'type': 'str',
                    'search_text': 'building_type',
                    'fallback': 'unknown'
                },
                'floor_area': {
                    'type': 'float',
                    'search_text': 'floor_area',
                    'fallback': 0.0
                },
                'year': {
                    'type': 'int',
                    'xpath': '@year',
                    'fallback': 2000
                }
            }
        }
        
        self.processor = CityGMLAttributeProcessor(
            config=self.config,
            namespaces=self.namespaces
        )
        
        # Test XML mit Gebäudeattributen
        self.test_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                       xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
                       xmlns:gml="http://www.opengis.net/gml"
                       gml:id="BLDG_1"
                       year="2010">
            <bldg:measuredHeight>15.5</bldg:measuredHeight>
            <gen:stringAttribute>
                <gen:name>building_type</gen:name>
                <gen:value>residential</gen:value>
            </gen:stringAttribute>
            <gen:doubleAttribute>
                <gen:name>floor_area</gen:name>
                <gen:value>150.5</gen:value>
            </gen:doubleAttribute>
        </bldg:Building>
        """
        self.building = etree.fromstring(self.test_xml.encode())
        
    def test_extract_building_attributes(self):
        """Test Extraktion aller Gebäudeattribute."""
        attributes = self.processor.extract_building_attributes(self.building)
        self.assertIsNotNone(attributes)
        
        # Prüfe extrahierte Werte
        self.assertEqual(attributes['measured_height'], 15.5)
        self.assertEqual(attributes['building_type'], 'residential')
        self.assertEqual(attributes['floor_area'], 150.5)
        self.assertEqual(attributes['year'], 2010)
        
    def test_extract_field_value(self):
        """Test Extraktion einzelner Feldwerte."""
        # Test XPath-Extraktion
        height = self.processor._extract_field_value(
            self.building,
            'measured_height',
            self.config['citygml_fields']['measured_height']
        )
        self.assertEqual(height, 15.5)
        
        # Test Attribut-Extraktion
        year = self.processor._extract_field_value(
            self.building,
            'year',
            self.config['citygml_fields']['year']
        )
        self.assertEqual(year, 2010)
        
        # Test generisches String-Attribut
        building_type = self.processor._extract_field_value(
            self.building,
            'building_type',
            self.config['citygml_fields']['building_type']
        )
        self.assertEqual(building_type, 'residential')
        
        # Test generisches Double-Attribut
        floor_area = self.processor._extract_field_value(
            self.building,
            'floor_area',
            self.config['citygml_fields']['floor_area']
        )
        self.assertEqual(floor_area, 150.5)
        
    def test_missing_required_fields(self):
        """Test Verhalten bei fehlenden Pflichtfeldern."""
        # Erstelle Gebäude ohne Pflichtfelder
        invalid_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                       xmlns:gml="http://www.opengis.net/gml"
                       gml:id="BLDG_2">
        </bldg:Building>
        """
        invalid_building = etree.fromstring(invalid_xml.encode())
        
        # Extraktion sollte None zurückgeben
        attributes = self.processor.extract_building_attributes(invalid_building)
        self.assertIsNone(attributes)
        
    def test_fallback_values(self):
        """Test Verwendung von Fallback-Werten."""
        # Erstelle Gebäude ohne Attribute aber mit ID
        minimal_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                       xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
                       xmlns:gml="http://www.opengis.net/gml"
                       gml:id="BLDG_3">
            <bldg:measuredHeight>12.0</bldg:measuredHeight>
            <gen:stringAttribute>
                <gen:name>building_type</gen:name>
                <gen:value>commercial</gen:value>
            </gen:stringAttribute>
        </bldg:Building>
        """
        minimal_building = etree.fromstring(minimal_xml.encode())
        
        attributes = self.processor.extract_building_attributes(minimal_building)
        self.assertIsNotNone(attributes)
        
        # Prüfe Fallback-Werte
        self.assertEqual(attributes['floor_area'], 0.0)  # Fallback für floor_area
        self.assertEqual(attributes['year'], 2000)  # Fallback für year
        
if __name__ == '__main__':
    unittest.main() 
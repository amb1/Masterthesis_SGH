"""
Tests für die CityGML-Client-Klasse.
"""

import unittest
from pathlib import Path
from lxml import etree
from pipeline.data_sources.citygml.client import CityGMLBaseClient, XMLResolver

class TestCityGMLBaseClient(unittest.TestCase):
    """Testklasse für CityGML-Client."""
    
    def setUp(self):
        """Test-Setup."""
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/2.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0'
        }
        self.client = CityGMLBaseClient(namespaces=self.namespaces)
        
        # Test XML
        self.test_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <CityModel xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                   xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
                   xmlns:gml="http://www.opengis.net/gml">
            <bldg:Building gml:id="BLDG_1">
                <bldg:measuredHeight>10.5</bldg:measuredHeight>
                <gen:stringAttribute>
                    <gen:name>building_type</gen:name>
                    <gen:value>residential</gen:value>
                </gen:stringAttribute>
                <gen:doubleAttribute>
                    <gen:name>floor_area</gen:name>
                    <gen:value>150.5</gen:value>
                </gen:doubleAttribute>
            </bldg:Building>
            <bldg:Building gml:id="BLDG_2">
                <bldg:measuredHeight>15.0</bldg:measuredHeight>
            </bldg:Building>
        </CityModel>
        """
        self.root = etree.fromstring(self.test_xml.encode())
        
    def test_find_buildings(self):
        """Test Gebäudesuche."""
        buildings = self.client.find_buildings(self.root)
        self.assertEqual(len(buildings), 2)
        self.assertEqual(buildings[0].get('{' + self.namespaces['gml'] + '}id'), 'BLDG_1')
        
    def test_get_attribute(self):
        """Test Attributextraktion mit XPath."""
        building = self.root.find('.//bldg:Building', self.namespaces)
        height = self.client.get_attribute(building, './/bldg:measuredHeight', default=None)
        self.assertEqual(height, '10.5')
        
        # Test nicht vorhandenes Attribut
        missing = self.client.get_attribute(building, './/bldg:nonexistent', default='default')
        self.assertEqual(missing, 'default')
        
    def test_get_generic_attribute(self):
        """Test Extraktion generischer Attribute."""
        building = self.root.find('.//bldg:Building', self.namespaces)
        
        # Test String-Attribut
        building_type = self.client.get_generic_attribute(building, 'building_type')
        self.assertEqual(building_type, 'residential')
        
        # Test Double-Attribut
        floor_area = self.client.get_generic_attribute(building, 'floor_area')
        self.assertEqual(floor_area, 150.5)
        
        # Test nicht vorhandenes Attribut
        missing = self.client.get_generic_attribute(building, 'nonexistent', default='default')
        self.assertEqual(missing, 'default')
        
    def test_xml_resolver(self):
        """Test XML Entity Resolver."""
        resolver = XMLResolver()
        
        # Test Umlaut-Auflösung
        result = resolver.resolve('uuml', None, None)
        self.assertIsNotNone(result)
        
        # Test unbekannte Entity
        result = resolver.resolve('unknown', None, None)
        self.assertIsNone(result)
        
if __name__ == '__main__':
    unittest.main() 
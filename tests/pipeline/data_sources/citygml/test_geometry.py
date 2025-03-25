"""
Tests für den CityGML-Geometrie-Prozessor.
"""

import unittest
import numpy as np
from lxml import etree
from shapely.geometry import Polygon, MultiPolygon
from pipeline.data_sources.citygml.geometry import CityGMLGeometryProcessor

class TestCityGMLGeometryProcessor(unittest.TestCase):
    """Testklasse für CityGML-Geometrie-Prozessor."""
    
    def setUp(self):
        """Test-Setup."""
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/2.0'
        }
        
        self.config = {
            'srs_name': 'EPSG:31256',
            'validation': {
                'min_area': 10.0,
                'max_angle': 80,
                'fix_invalid': True,
                'check_area': True,
                'remove_small': True
            }
        }
        
        self.processor = CityGMLGeometryProcessor(
            config=self.config,
            namespaces=self.namespaces
        )
        
        # Test XML mit Gebäudegeometrie
        self.test_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                       xmlns:gml="http://www.opengis.net/gml">
            <bldg:boundedBy>
                <bldg:GroundSurface>
                    <bldg:lod2MultiSurface>
                        <gml:MultiSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:MultiSurface>
                    </bldg:lod2MultiSurface>
                </bldg:GroundSurface>
            </bldg:boundedBy>
            <bldg:boundedBy>
                <bldg:RoofSurface>
                    <bldg:lod2MultiSurface>
                        <gml:MultiSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>0 0 10 10 0 10 10 10 10 0 10 10 0 0 10</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:MultiSurface>
                    </bldg:lod2MultiSurface>
                </bldg:RoofSurface>
            </bldg:boundedBy>
        </bldg:Building>
        """
        self.building = etree.fromstring(self.test_xml.encode())
        
    def test_extract_building_footprint(self):
        """Test Extraktion der Gebäudegrundfläche."""
        footprint = self.processor.extract_building_footprint(self.building)
        self.assertIsInstance(footprint, Polygon)
        self.assertEqual(footprint.area, 100.0)  # 10x10 Quadrat
        
    def test_extract_roof_surfaces(self):
        """Test Extraktion der Dachflächen."""
        surfaces = self.processor.extract_roof_surfaces(self.building)
        self.assertEqual(len(surfaces), 1)
        self.assertIsInstance(surfaces[0], np.ndarray)
        self.assertEqual(surfaces[0].shape, (5, 3))  # 5 Punkte mit je 3 Koordinaten
        
    def test_validate_polygon(self):
        """Test Polygon-Validierung."""
        # Gültiges Polygon
        valid_coords = [(0,0), (10,0), (10,10), (0,10), (0,0)]
        valid_polygon = Polygon(valid_coords)
        self.assertTrue(self.processor._validate_polygon(valid_polygon))
        
        # Zu kleines Polygon
        small_coords = [(0,0), (1,0), (1,1), (0,1), (0,0)]
        small_polygon = Polygon(small_coords)
        self.assertFalse(self.processor._validate_polygon(small_polygon))
        
    def test_validate_roof_coordinates(self):
        """Test Validierung der Dachkoordinaten."""
        # Gültige Dachfläche (45 Grad Neigung)
        valid_roof = np.array([
            [0, 0, 0],
            [10, 0, 10],
            [10, 10, 10],
            [0, 10, 0],
            [0, 0, 0]
        ])
        self.assertTrue(self.processor._validate_roof_coordinates(valid_roof))
        
        # Ungültige Dachfläche (zu steil)
        invalid_roof = np.array([
            [0, 0, 0],
            [1, 0, 10],
            [1, 1, 10],
            [0, 1, 0],
            [0, 0, 0]
        ])
        self.assertFalse(self.processor._validate_roof_coordinates(invalid_roof))
        
    def test_extract_3d_coordinates(self):
        """Test Extraktion von 3D-Koordinaten."""
        coord_text = "0 0 0 10 0 0 10 10 0 0 10 0 0 0 0"
        coords = self.processor._extract_3d_coordinates(coord_text)
        self.assertIsInstance(coords, np.ndarray)
        self.assertEqual(coords.shape, (5, 3))
        np.testing.assert_array_equal(coords[0], [0, 0, 0])
        
if __name__ == '__main__':
    unittest.main() 
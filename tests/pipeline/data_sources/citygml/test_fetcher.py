"""
Tests für den CityGML-Fetcher.
"""

import unittest
from pathlib import Path
import tempfile
import geopandas as gpd
from pipeline.data_sources.citygml.fetcher import ViennaCityGMLFetcher, fetch_citygml_buildings

class TestViennaCityGMLFetcher(unittest.TestCase):
    """Testklasse für CityGML-Fetcher."""
    
    def setUp(self):
        """Test-Setup."""
        self.config = {
            'namespaces': {
                'gml': 'http://www.opengis.net/gml',
                'bldg': 'http://www.opengis.net/citygml/building/2.0',
                'gen': 'http://www.opengis.net/citygml/generics/2.0'
            },
            'required_fields': ['measured_height', 'building_type'],
            'geometry': {
                'srs_name': 'EPSG:31256',
                'validation': {
                    'min_area': 10.0,
                    'max_angle': 80,
                    'fix_invalid': True,
                    'check_area': True,
                    'remove_small': True
                }
            },
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
                }
            }
        }
        
        # Erstelle temporäre CityGML-Datei
        self.test_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <CityModel xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
                   xmlns:gen="http://www.opengis.net/citygml/generics/2.0"
                   xmlns:gml="http://www.opengis.net/gml">
            <bldg:Building gml:id="BLDG_1">
                <bldg:measuredHeight>15.5</bldg:measuredHeight>
                <gen:stringAttribute>
                    <gen:name>building_type</gen:name>
                    <gen:value>residential</gen:value>
                </gen:stringAttribute>
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
            </bldg:Building>
            <bldg:Building gml:id="BLDG_2">
                <bldg:measuredHeight>12.0</bldg:measuredHeight>
                <gen:stringAttribute>
                    <gen:name>building_type</gen:name>
                    <gen:value>commercial</gen:value>
                </gen:stringAttribute>
                <bldg:boundedBy>
                    <bldg:GroundSurface>
                        <bldg:lod2MultiSurface>
                            <gml:MultiSurface>
                                <gml:surfaceMember>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>20 0 0 30 0 0 30 10 0 20 10 0 20 0 0</gml:posList>
                                            </gml:LinearRing>
                                        </gml:exterior>
                                    </gml:Polygon>
                                </gml:surfaceMember>
                            </gml:MultiSurface>
                        </bldg:lod2MultiSurface>
                    </bldg:GroundSurface>
                </bldg:boundedBy>
            </bldg:Building>
        </CityModel>
        """
        
        # Speichere Test-XML in temporärer Datei
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.gml"
        with open(self.test_file, "w", encoding="utf-8") as f:
            f.write(self.test_xml)
            
    def test_init(self):
        """Test Initialisierung."""
        fetcher = ViennaCityGMLFetcher(config=self.config)
        self.assertIsNotNone(fetcher.client)
        self.assertIsNotNone(fetcher.geometry_processor)
        self.assertIsNotNone(fetcher.attribute_processor)
        
    def test_process_citygml(self):
        """Test Verarbeitung einer CityGML-Datei."""
        fetcher = ViennaCityGMLFetcher(config=self.config)
        result = fetcher.process_citygml(self.test_file)
        
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 2)
        
        # Prüfe erste Gebäude
        self.assertEqual(result.iloc[0]['measured_height'], 15.5)
        self.assertEqual(result.iloc[0]['building_type'], 'residential')
        self.assertEqual(result.iloc[0].geometry.area, 100.0)
        
        # Prüfe zweites Gebäude
        self.assertEqual(result.iloc[1]['measured_height'], 12.0)
        self.assertEqual(result.iloc[1]['building_type'], 'commercial')
        self.assertEqual(result.iloc[1].geometry.area, 100.0)
        
    def test_invalid_file(self):
        """Test Verhalten bei ungültiger Datei."""
        fetcher = ViennaCityGMLFetcher(config=self.config)
        
        # Test mit nicht existierender Datei
        result = fetcher.process_citygml(Path(self.temp_dir) / "nonexistent.gml")
        self.assertIsNone(result)
        
        # Test mit ungültiger XML-Datei
        invalid_file = Path(self.temp_dir) / "invalid.gml"
        with open(invalid_file, "w", encoding="utf-8") as f:
            f.write("Invalid XML")
        result = fetcher.process_citygml(invalid_file)
        self.assertIsNone(result)
        
    def test_helper_function(self):
        """Test Hilfsfunktion."""
        output_dir = Path(self.temp_dir) / "output"
        output_dir.mkdir(exist_ok=True)
        
        result = fetch_citygml_buildings(
            str(self.test_file),
            str(output_dir),
            self.config
        )
        
        self.assertIsInstance(result, gpd.GeoDataFrame)
        self.assertEqual(len(result), 2)
        
        # Prüfe ob Ausgabedatei erstellt wurde
        output_file = output_dir / "buildings.gpkg"
        self.assertTrue(output_file.exists())
        
    def tearDown(self):
        """Aufräumen nach Tests."""
        import shutil
        shutil.rmtree(self.temp_dir)
        
if __name__ == '__main__':
    unittest.main() 
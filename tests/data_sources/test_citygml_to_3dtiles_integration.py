import unittest
from pathlib import Path
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon
import json
import os
import shutil
import xml.etree.ElementTree as etree

from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor
from pipeline.data_sources.mesh_converter import MeshConverter
from pipeline.data_sources.b3dm_generator import B3DMGenerator
from pipeline.data_sources.tileset_generator import TilesetGenerator

class TestCityGMLTo3DTilesIntegration(unittest.TestCase):
    """Integration-Tests für die CityGML zu 3D Tiles Konvertierung"""
    
    def setUp(self):
        """Test-Setup"""
        # Erstelle temporäres Verzeichnis
        self.test_dir = Path("tests/temp")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Konfiguriere CityGML-Prozessor
        self.config = {
            'fields': {
                'building_id': {
                    'type': 'string',
                    'xpath': './/gml:id',
                    'namespaces': {'gml': 'http://www.opengis.net/gml'}
                },
                'height': {
                    'type': 'float',
                    'xpath': './/gen:stringAttribute[@name="HoeheDach"]/gen:value/text()',
                    'namespaces': {
                        'gen': 'http://www.opengis.net/citygml/generics/1.0'
                    }
                }
            },
            'validation': {
                'min_area': 1.0,  # Mindestfläche in m²
                'max_angle': 80.0  # Maximaler Dachwinkel in Grad
            }
        }
        
        # Erstelle Test-GeoDataFrame
        self.test_buildings = gpd.GeoDataFrame(
            {
                'building_id': ['building_001'],
                'height': [10.0],
                'geometry': [
                    Polygon([
                        (0, 0), (0, 10),
                        (10, 10), (10, 0),
                        (0, 0)
                    ])
                ]
            },
            crs="EPSG:31256"
        )
        
        # Speichere Test-CityGML
        self.citygml_path = self.test_dir / "test.gml"
        self.processor = CityGMLBuildingProcessor(self.config)
        self.processor._save_as_citygml(self.test_buildings, self.citygml_path)
        
        # Initialisiere Konverter
        self.mesh_converter = MeshConverter()
        self.b3dm_generator = B3DMGenerator(self.test_dir / "b3dm")
        self.tileset_generator = TilesetGenerator(self.test_dir / "tileset")
        
    def tearDown(self):
        """Test-Cleanup"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_citygml_to_3dtiles_conversion(self):
        """Test der kompletten Konvertierung von CityGML zu 3D Tiles"""
        # Lese CityGML
        buildings = self.processor.process_citygml(self.citygml_path)
        self.assertIsNotNone(buildings)
        self.assertEqual(len(buildings), 1)
        
        # Konvertiere zu Mesh
        building = buildings.iloc[0]
        mesh = self.mesh_converter.polygon_to_mesh(
            building.geometry,
            building.height
        )
        self.assertIsNotNone(mesh)
        
        # Erstelle B3DM
        b3dm_path = self.b3dm_generator.create_b3dm(
            mesh,
            {
                'building_id': building.building_id,
                'height': building.height
            },
            building.building_id
        )
        self.assertTrue(b3dm_path.exists())
        
        # Erstelle Tileset
        tileset_path = self.tileset_generator.create_tileset(
            buildings,
            self.test_dir / "b3dm"
        )
        self.assertTrue(tileset_path.exists())
        
        # Prüfe Tileset-Struktur
        with open(tileset_path) as f:
            tileset = json.load(f)
            
        self.assertIn('asset', tileset)
        self.assertIn('version', tileset['asset'])
        self.assertEqual(tileset['asset']['version'], '1.0')
        
        self.assertIn('geometricError', tileset)
        self.assertGreater(tileset['geometricError'], 0)
        
        self.assertIn('root', tileset)
        self.assertIn('children', tileset['root'])
        self.assertEqual(len(tileset['root']['children']), 1)
        
        child = tileset['root']['children'][0]
        self.assertIn('content', child)
        self.assertIn('uri', child['content'])
        self.assertTrue(child['content']['uri'].endswith('.b3dm'))
        
    def test_geometry_validation(self):
        """Test der Geometrievalidierung"""
        # Erstelle CityGML mit ungültiger Geometrie
        invalid_buildings = gpd.GeoDataFrame(
            {
                'building_id': ['invalid_001'],
                'height': [10.0],
                'geometry': [
                    Polygon([
                        (0, 0), (0, 0.5),  # Zu kleine Fläche
                        (0.5, 0.5), (0.5, 0),
                        (0, 0)
                    ])
                ]
            },
            crs="EPSG:31256"
        )
        
        invalid_path = self.test_dir / "invalid.gml"
        self.processor._save_as_citygml(invalid_buildings, invalid_path)
        
        # Verarbeite CityGML
        buildings = self.processor.process_citygml(invalid_path)
        self.assertIsNotNone(buildings)
        self.assertEqual(len(buildings), 0)  # Keine gültigen Gebäude
        
    def test_roof_validation(self):
        """Test der Dachflächenvalidierung"""
        # Erstelle CityGML mit steiler Dachfläche
        steep_roof = """<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns="http://www.opengis.net/citygml/1.0"
          xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
          xmlns:gml="http://www.opengis.net/gml"
          xmlns:gen="http://www.opengis.net/citygml/generics/1.0">
    <cityObjectMember>
        <bldg:Building gml:id="steep_001">
            <gml:name>steep_001</gml:name>
            <gen:stringAttribute name="HoeheDach">
                <gen:value>10.0</gen:value>
            </gen:stringAttribute>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <bldg:RoofSurface>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>
                                                    0 0 0
                                                    0 10 0
                                                    5 5 20
                                                    0 0 0
                                                </gml:posList>
                                            </gml:LinearRing>
                                        </gml:exterior>
                                    </gml:Polygon>
                                </bldg:RoofSurface>
                            </gml:surfaceMember>
                        </gml:CompositeSurface>
                    </gml:exterior>
                </gml:Solid>
            </bldg:lod2Solid>
        </bldg:Building>
    </cityObjectMember>
</CityModel>"""
        
        steep_path = self.test_dir / "steep.gml"
        with open(steep_path, 'w', encoding='utf-8') as f:
            f.write(steep_roof)
            
        # Verarbeite CityGML
        buildings = self.processor.process_citygml(steep_path)
        self.assertIsNotNone(buildings)
        self.assertEqual(len(buildings), 0)  # Keine gültigen Gebäude
        
if __name__ == '__main__':
    unittest.main() 
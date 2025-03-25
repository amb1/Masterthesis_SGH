import unittest
import tempfile
from pathlib import Path
import json
import numpy as np

from pipeline.data_sources.tileset_generator import TilesetGenerator

class TestTilesetGenerator(unittest.TestCase):
    def setUp(self):
        # Erstelle temporäres Verzeichnis
        self.temp_dir = tempfile.mkdtemp()
        self.generator = TilesetGenerator(Path(self.temp_dir))
        
        # Erstelle Test-Gebäude
        self.test_buildings = [
            {
                "b3dm_path": "building_001.b3dm",
                "bounds": [0, 0, 0, 1, 1, 3],  # Gebäude 1
                "properties": {
                    "height": 3.0,
                    "type": "residential",
                    "year": 2020
                }
            },
            {
                "b3dm_path": "building_002.b3dm",
                "bounds": [2, 2, 0, 3, 3, 4],  # Gebäude 2
                "properties": {
                    "height": 4.0,
                    "type": "commercial",
                    "year": 2019
                }
            }
        ]
        
    def test_create_tileset(self):
        # Erstelle Tileset
        output_path = self.generator.create_tileset(
            self.test_buildings,
            geometric_error=500.0
        )
        
        # Prüfe Ergebnis
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "tileset.json")
        
        # Lade und prüfe JSON
        with open(output_path, 'r', encoding='utf-8') as f:
            tileset = json.load(f)
            
        # Prüfe Asset-Version
        self.assertEqual(tileset["asset"]["version"], "1.0")
        
        # Prüfe Root-Tile
        root = tileset["root"]
        self.assertEqual(root["geometricError"], 500.0)
        self.assertEqual(root["refine"], "ADD")
        
        # Prüfe Bounding Volume des Root-Tiles
        box = root["boundingVolume"]["box"]
        self.assertEqual(len(box), 12)  # [center_x, center_y, center_z, width/2, 0, 0, 0, height/2, 0, 0, 0, depth/2]
        
        # Prüfe Children
        children = root["children"]
        self.assertEqual(len(children), 2)
        
        # Prüfe erstes Kind
        child1 = children[0]
        self.assertEqual(child1["content"]["uri"], "building_001.b3dm")
        self.assertEqual(child1["geometricError"], 0)
        
        # Prüfe zweites Kind
        child2 = children[1]
        self.assertEqual(child2["content"]["uri"], "building_002.b3dm")
        self.assertEqual(child2["geometricError"], 0)
        
    def test_create_tileset_with_no_buildings(self):
        # Erstelle Tileset ohne Gebäude
        output_path = self.generator.create_tileset(
            [],
            geometric_error=500.0
        )
        
        # Prüfe Ergebnis
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        
        # Lade und prüfe JSON
        with open(output_path, 'r', encoding='utf-8') as f:
            tileset = json.load(f)
            
        # Prüfe Root-Tile
        root = tileset["root"]
        self.assertEqual(len(root["children"]), 0)
        
        # Prüfe Bounding Box (sollte 0 sein)
        box = root["boundingVolume"]["box"]
        self.assertEqual(box, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        
    def test_bounds_to_box_conversion(self):
        # Test-Bounds
        bounds = [1, 2, 3, 4, 6, 9]  # [min_x, min_y, min_z, max_x, max_y, max_z]
        
        # Konvertiere zu Box
        box = self.generator._bounds_to_box(bounds)
        
        # Erwartete Werte
        expected = [
            2.5, 4.0, 6.0,  # center (mittelpunkt zwischen min und max)
            1.5, 0, 0,      # width/2 axis
            0, 2.0, 0,      # height/2 axis
            0, 0, 3.0       # depth/2 axis
        ]
        
        # Prüfe Ergebnis
        np.testing.assert_array_almost_equal(box, expected)
        
    def tearDown(self):
        # Lösche temporäres Verzeichnis
        import shutil
        shutil.rmtree(self.temp_dir) 
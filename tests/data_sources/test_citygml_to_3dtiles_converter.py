import unittest
import tempfile
from pathlib import Path
import json
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon
import pandas as pd

from pipeline.data_sources.citygml_to_3dtiles_converter import CityGMLTo3DTilesConverter

class TestCityGMLTo3DTilesConverter(unittest.TestCase):
    def setUp(self):
        # Erstelle temporäres Verzeichnis
        self.temp_dir = Path(tempfile.mkdtemp())
        self.converter = CityGMLTo3DTilesConverter(self.temp_dir)
        
        # Erstelle Test-GeoDataFrame
        geometries = [
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),  # Gebäude 1
            Polygon([(2, 2), (3, 2), (3, 3), (2, 3)])   # Gebäude 2
        ]
        
        data = {
            'geometry': geometries,
            'height': [3.0, 4.0],
            'building_id': ['building_001', 'building_002'],
            'type': ['residential', 'commercial'],
            'year': [2020, 2019]
        }
        
        self.test_buildings = gpd.GeoDataFrame(
            data,
            crs="EPSG:25832"  # UTM Zone 32N
        )
        
    def test_convert(self):
        # Konvertiere Gebäude
        output_path = self.converter.convert(self.test_buildings)
        
        # Prüfe Ergebnis
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        self.assertEqual(output_path.name, "tileset.json")
        
        # Prüfe Verzeichnisstruktur
        buildings_dir = self.temp_dir / "buildings"
        self.assertTrue(buildings_dir.exists())
        self.assertTrue(buildings_dir.is_dir())
        
        # Prüfe B3DM-Dateien
        b3dm_files = list(buildings_dir.glob("*.b3dm"))
        self.assertEqual(len(b3dm_files), 2)
        
        # Prüfe Tileset
        with open(output_path, 'r', encoding='utf-8') as f:
            tileset = json.load(f)
            
        # Prüfe Asset-Version
        self.assertEqual(tileset["asset"]["version"], "1.0")
        
        # Prüfe Root-Tile
        root = tileset["root"]
        self.assertEqual(root["geometricError"], 500.0)
        self.assertEqual(root["refine"], "ADD")
        
        # Prüfe Children
        children = root["children"]
        self.assertEqual(len(children), 2)
        
        # Prüfe erstes Kind
        child1 = children[0]
        self.assertEqual(child1["content"]["uri"], "buildings/building_001.b3dm")
        self.assertEqual(child1["geometricError"], 0)
        
        # Prüfe zweites Kind
        child2 = children[1]
        self.assertEqual(child2["content"]["uri"], "buildings/building_002.b3dm")
        self.assertEqual(child2["geometricError"], 0)
        
    def test_convert_with_no_buildings(self):
        # Erstelle leeren GeoDataFrame
        empty_gdf = gpd.GeoDataFrame(
            columns=['geometry', 'height', 'building_id', 'type', 'year'],
            crs="EPSG:25832"
        )
        
        # Konvertiere leere Gebäudeliste
        output_path = self.converter.convert(empty_gdf)
        
        # Sollte None zurückgeben
        self.assertIsNone(output_path)
        
    def test_convert_with_invalid_building(self):
        # Erstelle GeoDataFrame mit ungültigem Gebäude
        geometries = [
            Polygon([(0, 0), (0, 0), (0, 0)])  # Ungültiges Polygon
        ]
        
        data = {
            'geometry': geometries,
            'height': [3.0],
            'building_id': ['building_001'],
            'type': ['residential'],
            'year': [2020]
        }
        
        invalid_buildings = gpd.GeoDataFrame(
            data,
            crs="EPSG:25832"
        )
        
        # Konvertiere ungültiges Gebäude
        output_path = self.converter.convert(invalid_buildings)
        
        # Sollte None zurückgeben
        self.assertIsNone(output_path)
        
    def tearDown(self):
        # Lösche temporäres Verzeichnis
        import shutil
        shutil.rmtree(self.temp_dir) 
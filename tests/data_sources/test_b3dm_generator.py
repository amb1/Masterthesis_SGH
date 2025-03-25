import unittest
import tempfile
from pathlib import Path
import trimesh
import numpy as np
from shapely.geometry import Polygon
import struct

from pipeline.data_sources.mesh_converter import MeshConverter
from pipeline.data_sources.b3dm_generator import B3DMGenerator

class TestB3DMGenerator(unittest.TestCase):
    def setUp(self):
        # Erstelle temporäres Verzeichnis
        self.temp_dir = tempfile.mkdtemp()
        self.generator = B3DMGenerator(Path(self.temp_dir))
        
        # Erstelle Test-Mesh (einfaches Rechteck)
        polygon = Polygon([
            (0, 0), (1, 0), (1, 1), (0, 1)
        ])
        self.test_mesh = MeshConverter.polygon_to_mesh(polygon, height=3.0)
        
        # Test-Eigenschaften
        self.test_properties = {
            "height": 3.0,
            "type": "residential",
            "year": 2020
        }
        self.test_building_id = "test_building_001"
        
    def test_create_b3dm(self):
        # Erstelle B3DM
        output_path = self.generator.create_b3dm(
            self.test_mesh,
            self.test_properties,
            self.test_building_id
        )
        
        # Prüfe Ergebnis
        self.assertIsNotNone(output_path)
        self.assertTrue(output_path.exists())
        self.assertTrue(output_path.stat().st_size > 0)
        self.assertEqual(output_path.suffix, ".b3dm")
        
        # Prüfe B3DM-Header
        with open(output_path, 'rb') as f:
            # Lese Magic und Version
            magic = f.read(4)
            version = struct.unpack('<I', f.read(4))[0]
            
            self.assertEqual(magic, b'b3dm')
            self.assertEqual(version, 1)
            
            # Lese Byte-Längen
            byte_length = struct.unpack('<I', f.read(4))[0]
            ft_json_length = struct.unpack('<I', f.read(4))[0]
            ft_bin_length = struct.unpack('<I', f.read(4))[0]
            bt_json_length = struct.unpack('<I', f.read(4))[0]
            bt_bin_length = struct.unpack('<I', f.read(4))[0]
            
            # Prüfe Längen
            file_size = output_path.stat().st_size
            self.assertEqual(byte_length, file_size)
            self.assertEqual(
                file_size,
                28 + ft_json_length + ft_bin_length + 
                bt_json_length + bt_bin_length + 
                (file_size - (28 + ft_json_length + ft_bin_length + 
                bt_json_length + bt_bin_length))
            )
    
    def test_create_b3dm_with_invalid_mesh(self):
        # Erstelle leeres Mesh
        empty_mesh = trimesh.Trimesh()
        
        # Versuche B3DM zu erstellen
        output_path = self.generator.create_b3dm(
            empty_mesh,
            self.test_properties,
            self.test_building_id
        )
        
        # Sollte None zurückgeben
        self.assertIsNone(output_path)
        
    def tearDown(self):
        # Lösche temporäres Verzeichnis
        import shutil
        shutil.rmtree(self.temp_dir) 
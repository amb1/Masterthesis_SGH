import unittest
from shapely.geometry import Polygon, MultiPolygon
import numpy as np
from pipeline.data_sources.mesh_converter import MeshConverter

class TestMeshConverter(unittest.TestCase):
    def test_simple_polygon_to_mesh(self):
        """Test der Konvertierung eines einfachen Rechtecks"""
        # Erstelle ein einfaches Rechteck
        coords = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        polygon = Polygon(coords)
        
        # Konvertiere zu Mesh
        mesh = MeshConverter.polygon_to_mesh(polygon, height=2.0)
        
        # Überprüfe ob Mesh erstellt wurde
        self.assertIsNotNone(mesh)
        
        # Überprüfe Mesh-Eigenschaften
        self.assertTrue(mesh.is_watertight)  # Mesh sollte wasserdicht sein
        self.assertEqual(len(mesh.vertices), 8)  # 4 Punkte unten, 4 oben
        self.assertEqual(len(mesh.faces), 12)    # 2 für oben/unten + 2*4 für Seiten

    def test_multipolygon_to_mesh(self):
        """Test der Konvertierung eines MultiPolygons"""
        # Erstelle zwei Rechtecke
        poly1 = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        poly2 = Polygon([(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)])
        multipoly = MultiPolygon([poly1, poly2])
        
        # Konvertiere zu Mesh
        mesh = MeshConverter.polygon_to_mesh(multipoly, height=2.0)
        
        # Überprüfe ob Mesh erstellt wurde
        self.assertIsNotNone(mesh)
        
        # Überprüfe Mesh-Eigenschaften
        self.assertTrue(mesh.is_watertight)
        self.assertEqual(len(mesh.vertices), 16)  # 8 Punkte pro Rechteck
        self.assertEqual(len(mesh.faces), 24)     # 12 Faces pro Rechteck

if __name__ == '__main__':
    unittest.main() 
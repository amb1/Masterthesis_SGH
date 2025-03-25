import trimesh
import numpy as np
from typing import Tuple, List, Optional, Union
from shapely.geometry import Polygon, MultiPolygon
import logging
from shapely.ops import triangulate

logger = logging.getLogger(__name__)

class MeshConverter:
    """Konvertiert Gebäudegeometrien in Meshes"""
    
    @staticmethod
    def polygon_to_mesh(geom: Union[Polygon, MultiPolygon], height: float = 10.0) -> Optional[trimesh.Trimesh]:
        """Konvertiert ein Polygon/MultiPolygon in ein Trimesh.
        
        Args:
            geom: Polygon oder MultiPolygon der Grundfläche
            height: Höhe des Gebäudes in Metern
            
        Returns:
            trimesh.Trimesh oder None bei Fehler
        """
        try:
            if isinstance(geom, Polygon):
                return MeshConverter._process_single_polygon(geom, height)
            elif isinstance(geom, MultiPolygon):
                return MeshConverter._process_multipolygon(geom, height)
            return None
        except Exception as e:
            logger.error(f"Fehler bei der Mesh-Konvertierung: {e}")
            return None

    @staticmethod
    def _process_single_polygon(poly: Polygon, height: float) -> trimesh.Trimesh:
        """Verarbeitet ein einzelnes Polygon zu einem Mesh."""
        # Trianguliere die Grundfläche
        triangles = list(triangulate(poly))
        
        # Sammle alle einzigartigen Vertices der Grundfläche
        vertices_2d = set()
        faces = []
        current_vertex_index = 0
        vertex_map = {}  # Mapping von 2D-Koordinaten zu Vertex-Index
        
        # Verarbeite jedes Dreieck
        for triangle in triangles:
            triangle_vertices = np.array(triangle.exterior.coords)[:-1]  # Ignoriere den letzten Punkt (gleich dem ersten)
            triangle_face = []
            
            for vertex in triangle_vertices:
                vertex_tuple = tuple(vertex)
                if vertex_tuple not in vertex_map:
                    vertex_map[vertex_tuple] = current_vertex_index
                    vertices_2d.add(vertex_tuple)
                    current_vertex_index += 1
                triangle_face.append(vertex_map[vertex_tuple])
            
            faces.append(triangle_face)
        
        # Konvertiere zu NumPy-Array und füge Z-Koordinate hinzu
        vertices_2d = np.array(list(vertices_2d))
        bottom_vertices = np.column_stack([vertices_2d, np.zeros(len(vertices_2d))])
        top_vertices = np.column_stack([vertices_2d, np.full(len(vertices_2d), height)])
        
        # Kombiniere alle Vertices
        vertices = np.vstack([bottom_vertices, top_vertices])
        
        # Erstelle Faces für die obere Fläche
        num_vertices = len(vertices_2d)
        top_faces = [[f + num_vertices for f in face] for face in faces]
        
        # Erstelle Seitenflächen
        side_faces = []
        for i in range(len(poly.exterior.coords) - 1):
            next_i = (i + 1) % (len(poly.exterior.coords) - 1)
            side_faces.extend([
                [i, next_i, next_i + num_vertices],
                [i, next_i + num_vertices, i + num_vertices]
            ])
        
        # Kombiniere alle Faces
        all_faces = np.array(faces + top_faces + side_faces)
        
        # Erstelle Mesh
        mesh = trimesh.Trimesh(vertices=vertices, faces=all_faces)
        
        # Stelle sicher, dass die Normalen nach außen zeigen
        mesh.fix_normals()
        
        return mesh

    @staticmethod
    def _process_multipolygon(multipoly: MultiPolygon, height: float) -> trimesh.Trimesh:
        """Verarbeitet ein MultiPolygon zu einem Mesh."""
        meshes = []
        for poly in multipoly.geoms:
            mesh = MeshConverter._process_single_polygon(poly, height)
            if mesh is not None:
                meshes.append(mesh)
        
        if not meshes:
            return None
            
        # Kombiniere alle Meshes
        combined_mesh = trimesh.util.concatenate(meshes)
        # Stelle sicher, dass die Normalen nach außen zeigen
        combined_mesh.fix_normals()
        
        return combined_mesh 
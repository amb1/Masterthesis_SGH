import json
import numpy as np
from pathlib import Path
import trimesh
from typing import Dict, Any, List, Optional, Tuple
import logging
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

from .mesh_converter import MeshConverter
from .b3dm_generator import B3DMGenerator
from .tileset_generator import TilesetGenerator

logger = logging.getLogger(__name__)

class CityGMLTo3DTilesConverter:
    """Konvertiert CityGML-Daten in 3D Tiles"""
    
    def __init__(self, output_dir: Path):
        """
        Initialisiert den Konverter.
        
        Args:
            output_dir: Ausgabeverzeichnis für die 3D Tiles
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Erstelle Unterverzeichnisse
        self.buildings_dir = self.output_dir / "buildings"
        self.buildings_dir.mkdir(exist_ok=True)
        
        # Initialisiere Komponenten
        self.mesh_converter = MeshConverter()
        self.b3dm_generator = B3DMGenerator(self.buildings_dir)
        self.tileset_generator = TilesetGenerator(self.output_dir)
        
    def convert(self, buildings_gdf: gpd.GeoDataFrame) -> Optional[Path]:
        """
        Konvertiert CityGML-Gebäude in 3D Tiles.
        
        Args:
            buildings_gdf: GeoDataFrame mit Gebäuden und folgenden Spalten:
                - geometry: Polygon/MultiPolygon der Grundfläche
                - height: Höhe des Gebäudes
                - building_id: Eindeutige ID des Gebäudes
                - Weitere Spalten werden als Eigenschaften übernommen
                
        Returns:
            Path zur erstellten tileset.json oder None bei Fehler
        """
        try:
            # Konvertiere jedes Gebäude
            buildings_info = []
            
            for idx, building in buildings_gdf.iterrows():
                logger.info(f"Verarbeite Gebäude {building.building_id}...")
                
                # Konvertiere zu Mesh
                mesh = self.mesh_converter.polygon_to_mesh(
                    building.geometry,
                    building.height
                )
                
                if mesh is None:
                    logger.warning(f"⚠️ Konnte kein Mesh für Gebäude {building.building_id} erstellen")
                    continue
                
                # Erstelle B3DM
                properties = building.to_dict()
                del properties['geometry']  # Entferne Geometrie aus Properties
                
                b3dm_path = self.b3dm_generator.create_b3dm(
                    mesh,
                    properties,
                    building.building_id
                )
                
                if b3dm_path is None:
                    logger.warning(f"⚠️ Konnte keine B3DM-Datei für Gebäude {building.building_id} erstellen")
                    continue
                
                # Berechne Bounds
                bounds = self._calculate_mesh_bounds(mesh)
                
                # Sammle Gebäudeinformationen
                buildings_info.append({
                    "b3dm_path": b3dm_path,
                    "bounds": bounds,
                    "properties": properties
                })
                
            if not buildings_info:
                logger.error("❌ Keine Gebäude konnten konvertiert werden")
                return None
                
            # Erstelle Tileset
            tileset_path = self.tileset_generator.create_tileset(
                buildings_info,
                geometric_error=500.0  # TODO: Berechne basierend auf Datensatz
            )
            
            if tileset_path is None:
                logger.error("❌ Konnte kein Tileset erstellen")
                return None
                
            logger.info(f"✅ Konvertierung abgeschlossen: {tileset_path}")
            return tileset_path
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Konvertierung: {str(e)}")
            return None
            
    def _calculate_mesh_bounds(self, mesh: trimesh.Trimesh) -> List[float]:
        """
        Berechnet die Bounding Box eines Meshes.
        
        Args:
            mesh: Das Mesh
            
        Returns:
            [min_x, min_y, min_z, max_x, max_y, max_z]
        """
        bounds = mesh.bounds
        return [
            bounds[0][0], bounds[0][1], bounds[0][2],  # min
            bounds[1][0], bounds[1][1], bounds[1][2]   # max
        ] 
import json
from pathlib import Path
import geopandas as gpd
import numpy as np
import logging
from typing import Dict, Any, Optional
import uuid

logger = logging.getLogger(__name__)

class TileSet:
    def __init__(self, asset=None, geometricError=None, root=None):
        self.asset = asset or {
            "version": "1.0",
            "generator": "SGH-Master Pipeline"
        }
        self.geometricError = geometricError or 500.0
        self.root = root or {}

    def to_dict(self):
        return {
            "asset": self.asset,
            "geometricError": self.geometricError,
            "root": self.root
        }

class TilesetGenerator:
    """Generiert 3D Tiles Tilesets"""
    
    def __init__(self, config=None):
        self.config = config or {}
        self.buildings = []
        
    def add_building(self, building):
        self.buildings.append(building)

    def create_tileset(
        self,
        buildings: gpd.GeoDataFrame,
        b3dm_dir: Path
    ) -> Optional[Path]:
        """
        Erstellt ein Tileset für die Gebäude.
        
        Args:
            buildings: GeoDataFrame mit Gebäuden
            b3dm_dir: Verzeichnis mit B3DM-Dateien
            
        Returns:
            Pfad zur tileset.json oder None bei Fehler
        """
        try:
            # Erstelle Tileset
            tileset = TileSet()
            
            # Gruppiere Gebäude nach Höhe
            height_groups = self._group_buildings_by_height(self.buildings)
            
            # Erstelle Kinder-Tiles für jede Höhengruppe
            children = []
            for height, buildings in height_groups.items():
                child = {
                    "boundingVolume": self._calculate_bounding_volume(buildings),
                    "geometricError": 100.0,
                    "content": {
                        "uri": f"buildings_{height}m.b3dm"
                    }
                }
                children.append(child)
            
            # Setze Root-Tile
            tileset.root = {
                "transform": [
                    1.0, 0.0, 0.0, 0.0,
                    0.0, 1.0, 0.0, 0.0,
                    0.0, 0.0, 1.0, 0.0,
                    0.0, 0.0, 0.0, 1.0
                ],
                "boundingVolume": self._calculate_bounding_volume(self.buildings),
                "geometricError": 500.0,
                "children": children
            }
            
            # Speichere Tileset
            output_path = self.config.get('output_dir') / "tileset.json"
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(tileset.to_dict(), f, indent=2)
                
            return output_path
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Tilesets: {str(e)}")
            return None
            
    def _calculate_bounding_volume(self, buildings):
        if not buildings:
            return {
                "box": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
            }

        coords = []
        for building in buildings:
            coords.extend(building.get("coordinates", []))
            
        if not coords:
            return {
                "box": [0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1]
            }
            
        coords = np.array(coords)
        center = np.mean(coords, axis=0)
        extents = np.max(coords, axis=0) - np.min(coords, axis=0)
        
        return {
            "box": [
                center[0], center[1], center[2],  # Center
                extents[0]/2, 0, 0,  # X half-width
                0, extents[1]/2, 0,  # Y half-width
                0, 0, extents[2]/2   # Z half-width
            ]
        }
        
    def _group_buildings_by_height(self, buildings):
        if not buildings:
            return []
            
        # Gruppiere Gebäude nach Höhe
        height_groups = {}
        for building in buildings:
            height = building.get("height", 0)
            height_group = int(height / 10) * 10  # Gruppiere in 10m-Schritten
            if height_group not in height_groups:
                height_groups[height_group] = []
            height_groups[height_group].append(building)
            
        return height_groups 
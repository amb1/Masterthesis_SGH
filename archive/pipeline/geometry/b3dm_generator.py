import os
import json
import numpy as np
import trimesh
from pathlib import Path
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class B3DMGenerator:
    """Generiert B3DM-Dateien aus Meshes"""
    
    def __init__(self, output_dir: Path):
        """
        Initialisiert den Generator.
        
        Args:
            output_dir: Ausgabeverzeichnis für B3DM-Dateien
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def create_b3dm(
        self,
        mesh: trimesh.Trimesh,
        properties: Dict[str, Any],
        building_id: str
    ) -> Optional[Path]:
        """
        Erstellt eine B3DM-Datei aus einem Mesh.
        
        Args:
            mesh: Das Mesh als trimesh.Trimesh
            properties: Dictionary mit Eigenschaften
            building_id: ID des Gebäudes
            
        Returns:
            Pfad zur B3DM-Datei oder None bei Fehler
        """
        try:
            # Prüfe Mesh
            if mesh is None or len(mesh.vertices) == 0:
                logger.warning("Ungültiges Mesh")
                return None
                
            # Erstelle GLB
            glb_path = self.output_dir / f"{building_id}.glb"
            mesh.export(str(glb_path), file_type='glb')
            
            # Erstelle Feature Table
            feature_table = {
                "BATCH_LENGTH": 1
            }
            feature_table_binary = b""
            
            # Erstelle Batch Table
            batch_table = properties
            batch_table_binary = b""
            
            # Lese GLB
            with open(glb_path, 'rb') as f:
                glb_data = f.read()
                
            # Erstelle B3DM Header
            header = bytearray(28)  # 28 Bytes Header
            
            # Magic: "b3dm"
            header[0:4] = b'b3dm'
            
            # Version: 1
            header[4:8] = (1).to_bytes(4, byteorder='little')
            
            # Gesamtlänge
            total_length = len(header) + len(feature_table_binary) + len(batch_table_binary) + len(glb_data)
            header[8:12] = total_length.to_bytes(4, byteorder='little')
            
            # Feature Table JSON Länge
            ft_json = json.dumps(feature_table).encode('utf-8')
            header[12:16] = len(ft_json).to_bytes(4, byteorder='little')
            
            # Feature Table Binary Länge
            header[16:20] = len(feature_table_binary).to_bytes(4, byteorder='little')
            
            # Batch Table JSON Länge
            bt_json = json.dumps(batch_table).encode('utf-8')
            header[20:24] = len(bt_json).to_bytes(4, byteorder='little')
            
            # Batch Table Binary Länge
            header[24:28] = len(batch_table_binary).to_bytes(4, byteorder='little')
            
            # Schreibe B3DM-Datei
            b3dm_path = self.output_dir / f"{building_id}.b3dm"
            with open(b3dm_path, 'wb') as f:
                f.write(header)
                f.write(ft_json)
                f.write(feature_table_binary)
                f.write(bt_json)
                f.write(batch_table_binary)
                f.write(glb_data)
                
            # Lösche temporäre GLB-Datei
            glb_path.unlink()
            
            return b3dm_path
            
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der B3DM-Datei: {str(e)}")
            return None 
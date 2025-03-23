"""
CityGML zu 3D Tiles Konverter
"""
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import xml.etree.ElementTree as ET
import py3dtiles
import numpy as np
from ..base import BaseConverter

logger = logging.getLogger(__name__)

class CityGMLConverter(BaseConverter):
    """Konvertiert CityGML-Dateien in 3D Tiles"""

    def __init__(self):
        """Initialisiert den Konverter"""
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0'
        }

    def convert(self, input_path: Path, output_path: Path) -> bool:
        """
        Konvertiert eine CityGML-Datei in 3D Tiles.

        Args:
            input_path: Pfad zur CityGML-Datei
            output_path: Ausgabeverzeichnis für 3D Tiles

        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Validiere Eingabe
            if not input_path.exists():
                logger.error(f"Eingabedatei nicht gefunden: {input_path}")
                return False

            # Erstelle Ausgabeverzeichnis
            output_path.mkdir(parents=True, exist_ok=True)

            # Parse CityGML
            tree = ET.parse(str(input_path))
            root = tree.getroot()

            # Finde CRS
            srs_name = root.find('.//gml:Envelope[@srsName]', self.namespaces)
            if srs_name is not None:
                srs = srs_name.attrib['srsName']
                if 'EPSG' in srs:
                    epsg = srs.split(':')[-1]
                    logger.info(f"Verwende CRS: EPSG:{epsg}")

            # Sammle Gebäude
            buildings = root.findall('.//bldg:Building', self.namespaces)
            all_geometries = []
            building_attributes = []

            logger.info(f"Verarbeite {len(buildings)} Gebäude...")

            for building in buildings:
                try:
                    # Extrahiere Gebäude-ID
                    gml_id = building.attrib['{http://www.opengis.net/gml}id']

                    # Extrahiere 3D-Geometrie
                    geometries = self._extract_building_geometry(building)
                    if geometries:
                        all_geometries.extend(geometries)

                        # Sammle Attribute
                        height = building.find('.//bldg:measuredHeight', self.namespaces)
                        building_height = float(height.text) if height is not None else None

                        building_attributes.append({
                            'id': gml_id,
                            'height': building_height
                        })

                except Exception as e:
                    logger.error(f"Fehler bei Gebäude {gml_id if 'gml_id' in locals() else 'unbekannt'}: {str(e)}")

            if not all_geometries:
                logger.error("Keine Geometrien gefunden!")
                return False

            # Erstelle Tileset
            tileset = py3dtiles.Tileset()
            root_tile = py3dtiles.Tile()

            # Füge Geometrien zum Root-Tile hinzu
            for geom, attrs in zip(all_geometries, building_attributes):
                # Konvertiere die Geometrie in das richtige Format
                vertices = np.array([point for polygon in geom for point in polygon], dtype=np.float32)
                faces = np.array([[i, i+1, i+2] for i in range(0, len(vertices)-2, 3)], dtype=np.uint32)

                # Füge die Geometrie zum Tile hinzu
                root_tile.add_geometry(vertices, faces)
                root_tile.add_batch_table_property('id', attrs['id'])
                if attrs['height'] is not None:
                    root_tile.add_batch_table_property('height', attrs['height'])

            # Füge den Root-Tile zum Tileset hinzu
            tileset.add_tile(root_tile)

            # Speichere das Tileset
            tileset_path = output_path / 'tileset.json'
            b3dm_path = output_path / 'tile.b3dm'

            # Speichere die B3DM-Datei
            with open(str(b3dm_path), 'wb') as f:
                f.write(root_tile.to_array())

            # Speichere das Tileset
            with open(str(tileset_path), 'w') as f:
                json.dump(tileset.to_dict(), f, indent=2)

            logger.info(f"3D Tiles erfolgreich erstellt in: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Fehler bei der Konvertierung: {str(e)}")
            return False

    def _extract_building_geometry(self, building: ET.Element) -> Optional[list]:
        """
        Extrahiert die 3D-Geometrie eines Gebäudes.

        Args:
            building: XML-Element des Gebäudes

        Returns:
            Optional[list]: Liste von 3D-Koordinaten oder None
        """
        try:
            # Suche nach LOD2 Solid
            solid = building.find('.//bldg:lod2Solid//gml:Solid', self.namespaces)
            if solid is not None:
                return self._extract_solid_geometry(solid)

            # Alternativ: Suche nach LOD2 MultiSurface
            multi_surface = building.find('.//bldg:lod2MultiSurface//gml:MultiSurface', self.namespaces)
            if multi_surface is not None:
                return self._extract_multisurface_geometry(multi_surface)

            return None

        except Exception as e:
            logger.error(f"Fehler bei der Geometrie-Extraktion: {str(e)}")
            return None

    def _extract_solid_geometry(self, solid: ET.Element) -> list:
        """
        Extrahiert Geometrie aus einem GML Solid.

        Args:
            solid: XML-Element des Solids

        Returns:
            list: Liste von 3D-Koordinaten
        """
        geometries = []
        for polygon in solid.findall('.//gml:Polygon', self.namespaces):
            coords = self._extract_polygon_coordinates(polygon)
            if coords:
                geometries.append(coords)
        return geometries

    def _extract_multisurface_geometry(self, multi_surface: ET.Element) -> list:
        """
        Extrahiert Geometrie aus einer GML MultiSurface.

        Args:
            multi_surface: XML-Element der MultiSurface

        Returns:
            list: Liste von 3D-Koordinaten
        """
        geometries = []
        for polygon in multi_surface.findall('.//gml:Polygon', self.namespaces):
            coords = self._extract_polygon_coordinates(polygon)
            if coords:
                geometries.append(coords)
        return geometries

    def _extract_polygon_coordinates(self, polygon: ET.Element) -> Optional[list]:
        """
        Extrahiert Koordinaten aus einem GML Polygon.

        Args:
            polygon: XML-Element des Polygons

        Returns:
            Optional[list]: Liste von 3D-Koordinaten oder None
        """
        try:
            coords = polygon.find('.//gml:coordinates', self.namespaces)
            if coords is not None:
                # Parse coordinates string
                coord_list = []
                for coord_str in coords.text.strip().split():
                    x, y, z = map(float, coord_str.split(','))
                    coord_list.append([x, y, z])
                return coord_list

            # Alternative: posList
            pos_list = polygon.find('.//gml:posList', self.namespaces)
            if pos_list is not None:
                coords = list(map(float, pos_list.text.strip().split()))
                return [[coords[i], coords[i+1], coords[i+2]] 
                       for i in range(0, len(coords), 3)]

            return None

        except Exception as e:
            logger.error(f"Fehler beim Parsen der Koordinaten: {str(e)}")
            return None 
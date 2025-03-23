"""
CityGML-Prozessor für die Verarbeitung von CityGML-Dateien und Integration mit Supabase.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import geopandas as gpd
import json
from shapely.geometry import shape, MultiPolygon, Polygon
from shapely.ops import transform
import py3dtiles
import numpy as np
from .db_utils import SupabaseManager
import xml.etree.ElementTree as ET
import pyproj
from shapely.ops import unary_union

class CityGMLProcessor:
    def __init__(self):
        # Basis-Verzeichnisse bestimmen
        self.script_dir = Path(__file__).resolve().parent
        self.project_root = self.script_dir.parent.parent.parent
        self.data_dir = self.project_root / 'local' / 'data'
        self.citygml_dir = self.data_dir / 'citygml'
        self.tiles_dir = self.data_dir / '3dtiles'
        
        # Stelle sicher, dass die Ausgabeverzeichnisse existieren
        self.tiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Supabase Manager initialisieren
        self.supabase = SupabaseManager()

    def extract_building_footprint(self, building_elem):
        """Extrahiert den Gebäudegrundriss aus dem CityGML-Element"""
        # Namespaces definieren
        ns = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/1.0'
        }
        
        try:
            # Versuche zuerst LOD2 Solid
            lod2_solid = building_elem.find('.//bldg:lod2Solid', ns)
            if lod2_solid is not None:
                return self._extract_solid_geometry(lod2_solid, ns)
            
            # Versuche dann LOD2 MultiSurface
            lod2_ms = building_elem.find('.//bldg:lod2MultiSurface', ns)
            if lod2_ms is not None:
                return self._extract_multisurface_geometry(lod2_ms, ns)
            
            # Fallback: Versuche direkte Koordinatenextraktion
            coords = []
            for pos_list in building_elem.findall('.//gml:posList', ns):
                values = [float(x) for x in pos_list.text.split()]
                points = [(values[i], values[i+1]) for i in range(0, len(values), 3)]
                if points:
                    coords.append(points)
            
            if coords:
                return Polygon(coords[0])
                
            return None
            
        except Exception as e:
            print(f"Fehler bei der Geometrieextraktion: {str(e)}")
            return None

    def _extract_solid_geometry(self, solid, ns):
        """Extrahiert die Geometrie aus einem Solid."""
        try:
            # Finde alle Exterior Surfaces
            surfaces = solid.findall('.//{http://www.opengis.net/gml}exterior//{http://www.opengis.net/gml}Polygon', ns)
            if not surfaces:
                return None

            # Extrahiere Koordinaten aus jeder Surface
            polygons = []
            for surface in surfaces:
                coords = self._extract_coordinates(surface, ns)
                if coords and len(coords) >= 3:
                    polygons.append(Polygon(coords))

            if not polygons:
                return None

            # Vereinige alle Polygone
            union = unary_union(polygons)
            if isinstance(union, Polygon):
                return union
            elif isinstance(union, MultiPolygon):
                # Nimm das größte Polygon
                return max(union.geoms, key=lambda p: p.area)
            
            return None
        except Exception as e:
            print(f"Fehler bei der Solid-Geometrieextraktion: {str(e)}")
            return None

    def _extract_multisurface_geometry(self, multisurface, ns):
        """Extrahiert die Geometrie aus einer MultiSurface."""
        try:
            surfaces = multisurface.findall('.//{http://www.opengis.net/gml}surfaceMember//{http://www.opengis.net/gml}Polygon', ns)
            if not surfaces:
                return None
            
            polygons = []
            for surface in surfaces:
                coords = self._extract_coordinates(surface, ns)
                if coords and len(coords) >= 3:
                    polygons.append(Polygon(coords))
            
            if not polygons:
                return None

            union = unary_union(polygons)
            if isinstance(union, Polygon):
                return union
            elif isinstance(union, MultiPolygon):
                return max(union.geoms, key=lambda p: p.area)
            
            return None
        except Exception as e:
            print(f"Fehler bei der MultiSurface-Geometrieextraktion: {str(e)}")
            return None

    def _extract_coordinates(self, polygon, ns):
        """Extrahiert Koordinaten aus einem Polygon."""
        try:
            # Versuche zuerst posList
            pos_list = polygon.find('.//{http://www.opengis.net/gml}posList', ns)
            if pos_list is not None and pos_list.text:
                coords = [float(x) for x in pos_list.text.split()]
                return [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            
            # Fallback: Versuche einzelne Koordinaten
            pos = polygon.findall('.//{http://www.opengis.net/gml}pos', ns)
            if pos:
                coords = []
                for p in pos:
                    if p.text:
                        values = [float(x) for x in p.text.split()]
                        coords.append((values[0], values[1]))
                return coords
            
            return None
        except Exception as e:
            print(f"Fehler bei der Koordinatenextraktion: {str(e)}")
            return None

    def process_citygml(self, citygml_filename: str):
        """Verarbeitet CityGML-Datei und speichert Daten in Supabase"""
        citygml_path = self.citygml_dir / citygml_filename
        
        if not citygml_path.exists():
            raise FileNotFoundError(f"CityGML Datei nicht gefunden: {citygml_path}")
        
        print(f"Verarbeite CityGML-Datei: {citygml_filename}")
        
        # Parse CityGML mit ElementTree
        tree = ET.parse(str(citygml_path))
        root = tree.getroot()
        
        # Namespaces aus der Konfiguration
        ns = {
            'core': 'http://www.opengis.net/citygml/2.0',
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0',
            'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0',
            'xlink': 'http://www.w3.org/1999/xlink',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        # Finde das CRS
        srs_name = root.find('.//gml:Envelope[@srsName]', ns)
        if srs_name is not None:
            srs = srs_name.attrib['srsName']
            if 'EPSG' in srs:
                epsg = srs.split(':')[-1]
                print(f"Gefundenes CRS: EPSG:{epsg}")
        
        # Versuche verschiedene XPath-Ausdrücke für Gebäude
        buildings = []
        xpath_patterns = [
            './/bldg:Building',
            './/Building',
            './/{http://www.opengis.net/citygml/building/2.0}Building',
            './/{http://www.opengis.net/citygml/building/1.0}Building'
        ]
        
        for pattern in xpath_patterns:
            try:
                buildings = root.findall(pattern, ns)
                if buildings:
                    print(f"Gebäude gefunden mit Pattern: {pattern}")
                    break
            except Exception as e:
                print(f"Pattern {pattern} fehlgeschlagen: {str(e)}")
        
        print(f"Gefundene Gebäude: {len(buildings)}")
        
        processed_buildings = []
        for building in buildings:
            try:
                # Extrahiere Gebäude-ID (required)
                gml_id = building.attrib['{http://www.opengis.net/gml}id']
                
                # Extrahiere Grundriss
                footprint = self.extract_building_footprint(building)
                if footprint is None:
                    print(f"Konnte keinen Grundriss für Gebäude {gml_id} extrahieren")
                    continue
                
                # Required Attribute
                height = building.find('.//bldg:measuredHeight', ns)
                building_height = float(height.text) if height is not None else None
                
                storeys = building.find('.//bldg:storeysAboveGround', ns)
                storeys_above_ground = int(storeys.text) if storeys is not None else None
                
                # Optional Attribute
                function = building.find('.//bldg:function', ns)
                building_function = function.text if function is not None else None
                
                usage = building.find('.//bldg:usage', ns)
                building_usage = usage.text if usage is not None else None
                
                # OBJECTID aus generischen Attributen
                object_id = building.find('.//gen:stringAttribute[@name="OBJECTID"]', ns)
                building_object_id = object_id.text if object_id is not None else None
                
                # Attribute für die Datenbank vorbereiten
                building_attributes = {
                    'height': building_height,
                    'storeys': storeys_above_ground,
                    'building_type': building_function or building_usage,
                    'object_id': building_object_id
                }
                
                # Speichere in Datenbank
                try:
                    result = self.supabase.insert_building(
                        gml_id=gml_id,
                        geometry=footprint,
                        attributes=building_attributes
                    )
                    
                    if result:
                        print(f"Gebäude {gml_id} erfolgreich gespeichert")
                        processed_buildings.append({
                            'gml_id': gml_id,
                            'geometry': footprint,
                            **building_attributes
                        })
                        
                        # WFS-Daten abrufen und speichern
                        wfs_data = self.get_wfs_data(footprint)
                        if wfs_data:
                            self.supabase.insert_wfs_data(
                                building_id=result['id'],  # Verwende die ID aus dem Ergebnis
                                data_type='energiebedarf',
                                attributes=wfs_data,
                                geometry=footprint
                            )
                        
                        # CEA-Input generieren und speichern
                        cea_data = self.generate_cea_input(building_attributes)
                        if cea_data:
                            self.supabase.insert_cea_input(
                                building_id=result['id'],  # Verwende die ID aus dem Ergebnis
                                file_type='zone',
                                data=cea_data
                            )
                except Exception as db_error:
                    print(f"Datenbankfehler bei Gebäude {gml_id}: {str(db_error)}")
                    continue
                
            except Exception as e:
                print(f"Fehler bei der Verarbeitung von Gebäude {gml_id if 'gml_id' in locals() else 'unbekannt'}: {str(e)}")
                continue
        
        return processed_buildings

    def get_wfs_data(self, geometry):
        """WFS-Daten für ein Gebäude abrufen"""
        # TODO: Implementierung der WFS-Abfrage
        return {
            'heizwärmebedarf': 100.0,
            'warmwasserbedarf': 25.0
        }

    def generate_cea_input(self, building):
        """CEA-Input-Daten für ein Gebäude generieren"""
        return {
            'zone_type': 'residential',
            'use_type': 'MFH' if building.get('height', 0) > 10 else 'EFH'
        }

    def extract_building_geometry(self, building_elem, ns):
        """Extrahiert die vollständige 3D-Geometrie eines Gebäudes"""
        geometries = []
        # Suche nach allen Solid-Geometrien
        for solid in building_elem.findall('.//gml:Solid//gml:posList', ns):
            coords = []
            values = [float(x) for x in solid.text.split()]
            # Gruppiere in 3D-Koordinaten
            points = [(values[i], values[i+1], values[i+2]) for i in range(0, len(values), 3)]
            if points:
                coords.append(points)
                geometries.append(coords)
        return geometries

    def convert_to_3dtiles(self, citygml_filename: str, processed_buildings=None):
        """Konvertiert CityGML zu 3D Tiles"""
        citygml_path = self.citygml_dir / citygml_filename
        tiles_output = self.tiles_dir / citygml_filename.replace('.gml', '')
        
        print(f"Konvertiere {citygml_path} zu 3D Tiles")
        print(f"Ausgabe in: {tiles_output}")
        
        # Stelle sicher, dass das Ausgabeverzeichnis existiert
        tiles_output.mkdir(parents=True, exist_ok=True)
        
        # Parse CityGML wenn keine verarbeiteten Gebäude übergeben wurden
        if processed_buildings is None:
            tree = ET.parse(str(citygml_path))
            root = tree.getroot()
            
            # Namespaces
            ns = {
                'gml': 'http://www.opengis.net/gml',
                'bldg': 'http://www.opengis.net/citygml/building/1.0',
                'gen': 'http://www.opengis.net/citygml/generics/2.0'
            }
            
            # Finde das CRS
            srs_name = root.find('.//gml:Envelope[@srsName]', ns)
            if srs_name is not None:
                srs = srs_name.attrib['srsName']
                if 'EPSG' in srs:
                    epsg = srs.split(':')[-1]
                    print(f"Verwende CRS: EPSG:{epsg}")
            
            # Sammle alle Gebäudegeometrien
            buildings = root.findall('.//bldg:Building', ns)
            all_geometries = []
            building_attributes = []
            
            print(f"Verarbeite {len(buildings)} Gebäude für 3D Tiles...")
            
            for building in buildings:
                try:
                    # Extrahiere Gebäude-ID
                    gml_id = building.attrib['{http://www.opengis.net/gml}id']
                    
                    # Extrahiere 3D-Geometrie
                    geometries = self.extract_building_geometry(building, ns)
                    if geometries:
                        all_geometries.extend(geometries)
                        
                        # Sammle Attribute
                        height = building.find('.//bldg:measuredHeight', ns)
                        building_height = float(height.text) if height is not None else None
                        
                        building_attributes.append({
                            'id': gml_id,
                            'height': building_height
                        })
                        
                except Exception as e:
                    print(f"Fehler bei der 3D-Konvertierung von Gebäude {gml_id if 'gml_id' in locals() else 'unbekannt'}: {str(e)}")
        else:
            # Verwende die bereits verarbeiteten Gebäude
            all_geometries = []
            building_attributes = []
            
            print(f"Verarbeite {len(processed_buildings)} Gebäude für 3D Tiles...")
            
            for building in processed_buildings:
                try:
                    # Extrahiere 3D-Geometrie aus dem verarbeiteten Gebäude
                    if building['geometry']:
                        coords = list(building['geometry'].exterior.coords)
                        # Füge Z-Koordinate hinzu (Höhe des Gebäudes oder Standardhöhe)
                        height = building.get('height', 10.0)  # Standardhöhe von 10m wenn keine Höhe angegeben
                        ground_coords = [(x, y, 0) for x, y in coords]
                        roof_coords = [(x, y, height) for x, y in coords]
                        all_geometries.append([ground_coords + roof_coords])
                        
                        building_attributes.append({
                            'id': building['gml_id'],
                            'height': height
                        })
                        
                except Exception as e:
                    print(f"Fehler bei der 3D-Konvertierung von Gebäude {building.get('gml_id', 'unbekannt')}: {str(e)}")
        
        if not all_geometries:
            print("Keine Geometrien gefunden für die Konvertierung!")
            return
        
        try:
            # Erstelle Tileset
            tileset = py3dtiles.Tileset()
            
            # Erstelle einen Root-Tile
            root_tile = py3dtiles.Tile()
            
            # Füge Geometrien zum Root-Tile hinzu
            for geom, attrs in zip(all_geometries, building_attributes):
                # Konvertiere die Geometrie in das richtige Format
                vertices = np.array([point for polygon in geom for point in polygon], dtype=np.float32)
                
                # Erstelle Faces (Dreiecke) - hier vereinfacht
                faces = np.array([[i, i+1, i+2] for i in range(0, len(vertices)-2, 3)], dtype=np.uint32)
                
                # Füge die Geometrie zum Tile hinzu
                root_tile.add_geometry(vertices, faces)
                
                # Füge Attribute hinzu
                root_tile.add_batch_table_property('id', attrs['id'])
                if attrs['height'] is not None:
                    root_tile.add_batch_table_property('height', attrs['height'])
            
            # Füge den Root-Tile zum Tileset hinzu
            tileset.add_tile(root_tile)
            
            # Speichere das Tileset
            tileset_path = tiles_output / 'tileset.json'
            b3dm_path = tiles_output / 'tile.b3dm'
            
            # Speichere die B3DM-Datei
            with open(str(b3dm_path), 'wb') as f:
                f.write(root_tile.to_array())
            
            # Speichere das Tileset
            with open(str(tileset_path), 'w') as f:
                json.dump(tileset.to_dict(), f, indent=2)
            
            print(f"3D Tiles erfolgreich erstellt in: {tiles_output}")
            
        except Exception as e:
            print(f"Fehler bei der 3D Tiles Erstellung: {str(e)}")

def main():
    processor = CityGMLProcessor()
    
    # Verarbeite spezifische CityGML-Datei
    citygml_filename = "099082.gml"  # Angepasst an den tatsächlichen Dateinamen
    
    try:
        # CityGML verarbeiten und in Datenbank speichern
        processed_buildings = processor.process_citygml(citygml_filename)
        
        # 3D Tiles generieren mit den verarbeiteten Gebäuden
        processor.convert_to_3dtiles(citygml_filename, processed_buildings)
        
        print("Verarbeitung erfolgreich abgeschlossen")
        
    except Exception as e:
        print(f"Fehler bei der Verarbeitung: {str(e)}")

if __name__ == "__main__":
    main() 
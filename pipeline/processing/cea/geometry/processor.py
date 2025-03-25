"""
Geometrie-Prozessor für CEA-Daten.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from ...geometry_processor import GeometryProcessor
import os

class CEAGeometryProcessor(GeometryProcessor):
    """
    Erweitert den Basis-Geometrieprozessor um CEA-spezifische Funktionen.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._simplified_geometries = {}
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Geometrie und berechnet CEA-spezifische Attribute.
        """
        # Basis-Geometrieverarbeitung
        processed = super().process(data)
        if not processed:
            return {}
            
        try:
            # Konvertiere zu GeoDataFrame für einfachere Verarbeitung
            gdf = gpd.GeoDataFrame([processed])
            
            # Berechne CEA-spezifische Attribute
            gdf = self.calculate_cea_attributes(gdf)
            
            # Konvertiere zurück zu Dict
            result = gdf.to_dict('records')[0]
            
            # Füge zusätzliche CEA-Attribute hinzu
            result.update({
                'height': self._calculate_height(data),
                'orientation': self._calculate_orientation(gdf.geometry.iloc[0]),
                'footprint': self._calculate_footprint(gdf.geometry.iloc[0])
            })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Fehler bei der CEA-Geometrieverarbeitung: {str(e)}")
            return {}
            
    def simplify_geometry(self, geometry: Polygon) -> Polygon:
        """
        Vereinfacht eine Geometrie mit Caching und Validierung.
        """
        if not geometry or not geometry.is_valid:
            self.logger.warning("Ungültige Geometrie übergeben")
            return geometry
            
        geom_id = id(geometry)
        if geom_id not in self._simplified_geometries:
            try:
                # Prüfe Ausgangsgeometrie
                if geometry.area <= 0:
                    self.logger.warning(f"Geometrie hat Fläche {geometry.area}m², überspringe Vereinfachung")
                    self._simplified_geometries[geom_id] = geometry
                    return geometry
                    
                # Vereinfache mit zunehmender Toleranz
                for tolerance in [self.simplify_tolerance, self.simplify_tolerance * 2]:
                    simplified = geometry.simplify(tolerance)
                    if simplified and simplified.is_valid and simplified.area > 0:
                        self._simplified_geometries[geom_id] = simplified
                        return simplified
                        
                self.logger.warning("Vereinfachung fehlgeschlagen, verwende Original")
                self._simplified_geometries[geom_id] = geometry
                
            except Exception as e:
                self.logger.warning(f"Fehler bei Geometrievereinfachung: {str(e)}")
                self._simplified_geometries[geom_id] = geometry
                
        return self._simplified_geometries[geom_id]
            
    def calculate_cea_attributes(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Berechnet CEA-spezifische geometrische Attribute.
        """
        try:
            # Berechne Footprint
            bounds = gdf.geometry.bounds
            gdf['footprint'] = bounds.apply(
                lambda x: {
                    'min_x': x.minx,
                    'min_y': x.miny,
                    'max_x': x.maxx,
                    'max_y': x.maxy,
                    'width': x.maxx - x.minx,
                    'length': x.maxy - x.miny
                },
                axis=1
            )
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"Fehler bei CEA-Attributberechnung: {str(e)}")
            return gdf
            
    def _calculate_height(self, data: Dict[str, Any]) -> float:
        """Berechnet die Gebäudehöhe aus Z-Koordinaten oder Attributen."""
        if 'height' in data:
            return float(data['height'])
        
        z_coords = [p[2] for ring in data.get('coordinates', []) for p in ring if len(p) > 2]
        if z_coords:
            return max(z_coords) - min(z_coords)
            
        return self.config.get('default_building_height', 12.0)
        
    def _calculate_orientation(self, polygon: Polygon) -> float:
        """Berechnet die Hauptorientierung des Gebäudes in Grad."""
        if not polygon or not polygon.is_valid:
            self.logger.warning("Ungültige Geometrie für Orientierungsberechnung")
            return 0.0
            
        try:
            # Prüfe Geometrie
            if polygon.area <= 0:
                self.logger.warning("Polygon hat keine Fläche, überspringe Orientierungsberechnung")
                return 0.0
            
            rect = polygon.minimum_rotated_rectangle
            coords = list(rect.exterior.coords)
            
            angles = []
            for i in range(len(coords)-1):
                dx = coords[i+1][0] - coords[i][0]
                dy = coords[i+1][1] - coords[i][1]
                angle = np.degrees(np.arctan2(dy, dx)) % 180
                angles.append(angle)
                
            longest_idx = np.argmax([
                (coords[i+1][0] - coords[i][0])**2 + 
                (coords[i+1][1] - coords[i][1])**2 
                for i in range(len(coords)-1)
            ])
            
            return angles[longest_idx]
        except Exception as e:
            self.logger.warning(f"Fehler bei Orientierungsberechnung: {str(e)}")
            return 0.0

    def _calculate_footprint(self, polygon: Polygon) -> Dict[str, float]:
        """Berechnet den Footprint des Gebäudes."""
        if not polygon or not polygon.is_valid:
            self.logger.warning("Ungültige Geometrie für Footprint-Berechnung")
            return {
                'min_x': 0.0, 'min_y': 0.0,
                'max_x': 0.0, 'max_y': 0.0,
                'width': 0.0, 'length': 0.0,
                'area': 0.0
            }
            
        try:
            # Prüfe Geometrie
            if polygon.area <= 0:
                self.logger.warning("Polygon hat keine Fläche, überspringe Footprint-Berechnung")
                return {
                    'min_x': 0.0, 'min_y': 0.0,
                    'max_x': 0.0, 'max_y': 0.0,
                    'width': 0.0, 'length': 0.0,
                    'area': 0.0
                }
            
            bounds = polygon.bounds
            return {
                'min_x': bounds[0],
                'min_y': bounds[1],
                'max_x': bounds[2],
                'max_y': bounds[3],
                'width': bounds[2] - bounds[0],
                'length': bounds[3] - bounds[1],
                'area': polygon.area
            }
        except Exception as e:
            self.logger.warning(f"Fehler bei Footprint-Berechnung: {str(e)}")
            return {
                'min_x': 0.0, 'min_y': 0.0,
                'max_x': 0.0, 'max_y': 0.0,
                'width': 0.0, 'length': 0.0,
                'area': 0.0
            }

    def save_to_file(self, gdf: gpd.GeoDataFrame, output_path: str) -> bool:
        """
        Speichert den GeoDataFrame sicher in eine Datei.
        """
        temp_path = output_path + '.tmp'
        backup_path = output_path + '.bak'
        
        try:
            # Erstelle Ausgabeverzeichnis falls nicht vorhanden
            output_dir = os.path.dirname(output_path)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Speichere in temporäre Datei
            gdf.to_file(temp_path, driver='GeoJSON')
            
            # Versuche direkte Umbenennung
            try:
                if os.path.exists(output_path):
                    os.rename(output_path, backup_path)
                os.rename(temp_path, output_path)
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                return True
                
            except PermissionError:
                self.logger.warning(f"Datei {output_path} ist gesperrt, versuche alternative Methode")
                # Versuche alternative Speichermethode
                try:
                    with open(temp_path, 'rb') as src, open(output_path, 'wb') as dst:
                        dst.write(src.read())
                    os.remove(temp_path)
                    return True
                except Exception as e:
                    self.logger.error(f"Alternative Speichermethode fehlgeschlagen: {str(e)}")
                    raise
                
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Datei {output_path}: {str(e)}")
            # Aufräumen
            for path in [temp_path, backup_path]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass
            return False 
"""
Geometrie-Prozessor für CEA-Daten.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from ...geometry_processor import GeometryProcessor

class CEAGeometryProcessor(GeometryProcessor):
    """
    Erweitert den Basis-Geometrieprozessor um CEA-spezifische Funktionen.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
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

    def _calculate_footprint(self, polygon: Polygon) -> Dict[str, float]:
        """Berechnet den Footprint des Gebäudes."""
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
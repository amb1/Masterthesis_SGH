"""
OSM-Client für den Zugriff auf OpenStreetMap-Daten.
"""

import logging
from typing import Dict, Any, Optional, List, Union
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

logger = logging.getLogger(__name__)

class OSMClient:
    """Client für den Zugriff auf OpenStreetMap-Daten."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den OSM-Client.
        
        Args:
            config: Optionale Konfiguration
        """
        self.config = config or {}
        
    def get_buildings(self, polygon: Union[Polygon, MultiPolygon], tags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ruft Gebäude von OSM ab.
        
        Args:
            polygon: Polygon für die Abfrage
            tags: Optionale Tags für die Filterung
            
        Returns:
            Dict mit Features im GeoJSON-Format
        """
        try:
            # Standard-Tags für Gebäude
            building_tags = tags or {'building': True}
            
            # Hole Gebäude von OSM
            buildings = ox.features_from_polygon(
                polygon,
                tags=building_tags
            )
            
            if buildings.empty:
                return {'features': []}
                
            # Konvertiere zu GeoJSON
            buildings_json = buildings.to_crs(epsg=4326).__geo_interface__
            
            return {
                'features': buildings_json['features']
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Gebäude: {str(e)}")
            return {'features': []}
            
    def get_streets(self, polygon: Union[Polygon, MultiPolygon], tags: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ruft Straßen von OSM ab.
        
        Args:
            polygon: Polygon für die Abfrage
            tags: Optionale Tags für die Filterung
            
        Returns:
            Dict mit Features im GeoJSON-Format
        """
        try:
            # Standard-Tags für Straßen
            street_tags = tags or {
                'highway': ['residential', 'primary', 'secondary', 'tertiary', 'unclassified']
            }
            
            # Hole Straßen von OSM
            streets = ox.features_from_polygon(
                polygon,
                tags=street_tags
            )
            
            if streets.empty:
                return {'features': []}
                
            # Konvertiere zu GeoJSON
            streets_json = streets.to_crs(epsg=4326).__geo_interface__
            
            return {
                'features': streets_json['features']
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Straßen: {str(e)}")
            return {'features': []}
            
    def get_feature_info(self, feature_type: str) -> Dict[str, Any]:
        """
        Ruft Informationen über einen Feature-Typ ab.
        
        Args:
            feature_type: Art der Features ('buildings' oder 'streets')
            
        Returns:
            Dict mit Feature-Informationen
        """
        info = {
            'buildings': {
                'name': 'buildings',
                'description': 'OSM-Gebäude',
                'properties': {
                    'building': {'type': 'string', 'description': 'Gebäudetyp'},
                    'height': {'type': 'number', 'description': 'Gebäudehöhe'},
                    'levels': {'type': 'number', 'description': 'Anzahl Stockwerke'},
                    'name': {'type': 'string', 'description': 'Gebäudename'}
                }
            },
            'streets': {
                'name': 'streets',
                'description': 'OSM-Straßen',
                'properties': {
                    'highway': {'type': 'string', 'description': 'Straßentyp'},
                    'name': {'type': 'string', 'description': 'Straßenname'},
                    'lanes': {'type': 'number', 'description': 'Anzahl Fahrspuren'},
                    'surface': {'type': 'string', 'description': 'Oberflächentyp'}
                }
            }
        }
        
        try:
            return info.get(feature_type, {})
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Feature-Informationen: {str(e)}")
            return {} 
"""
OSM-Stream-Verarbeitung für große Datenmengen.
"""

import logging
from typing import Dict, Any, Iterator, Optional, List
import osmnx as ox
from shapely.geometry import Polygon, MultiPolygon

logger = logging.getLogger(__name__)

class OSMStream:
    """Klasse für das Streaming von OSM-Daten."""
    
    def __init__(self, chunk_size: int = 1000):
        """
        Initialisiert den OSM-Stream.
        
        Args:
            chunk_size: Anzahl Features pro Chunk
        """
        self.chunk_size = chunk_size
        
    def stream_features(self, polygon: Polygon, tags: Dict[str, Any], 
                       subdivide: bool = True) -> Iterator[Dict[str, Any]]:
        """
        Streamt Features von OSM.
        
        Args:
            polygon: Polygon für die Abfrage
            tags: Tags für die Filterung
            subdivide: Ob das Polygon unterteilt werden soll
            
        Yields:
            Dict: Ein Feature als GeoJSON
        """
        try:
            # Hole alle Features auf einmal
            features = ox.features_from_polygon(
                polygon,
                tags=tags
            )
            
            if features.empty:
                return
                
            # Konvertiere zu GeoJSON
            features_json = features.to_crs(epsg=4326).__geo_interface__
            
            # Streame Features in Chunks
            features_list = features_json['features']
            for i in range(0, len(features_list), self.chunk_size):
                chunk = features_list[i:i + self.chunk_size]
                for feature in chunk:
                    yield feature
                    
        except Exception as e:
            logger.error(f"❌ Fehler beim Streaming der Features: {str(e)}")
            return None
            
    def stream_buildings(self, polygon: Polygon, subdivide: bool = True) -> Iterator[Dict[str, Any]]:
        """
        Streamt Gebäude von OSM.
        
        Args:
            polygon: Polygon für die Abfrage
            subdivide: Ob das Polygon unterteilt werden soll
            
        Yields:
            Dict: Ein Gebäude-Feature als GeoJSON
        """
        try:
            # Standard-Tags für Gebäude
            building_tags = {'building': True}
            
            # Streame Features
            yield from self.stream_features(polygon, building_tags, subdivide)
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Streaming der Gebäude: {str(e)}")
            return None
            
    def stream_streets(self, polygon: Polygon, subdivide: bool = True) -> Iterator[Dict[str, Any]]:
        """
        Streamt Straßen von OSM.
        
        Args:
            polygon: Polygon für die Abfrage
            subdivide: Ob das Polygon unterteilt werden soll
            
        Yields:
            Dict: Ein Straßen-Feature als GeoJSON
        """
        try:
            # Standard-Tags für Straßen
            street_tags = {
                'highway': ['residential', 'primary', 'secondary', 'tertiary', 'unclassified']
            }
            
            # Streame Features
            yield from self.stream_features(polygon, street_tags, subdivide)
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Streaming der Straßen: {str(e)}")
            return None 
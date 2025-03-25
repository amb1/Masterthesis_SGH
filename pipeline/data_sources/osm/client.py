"""
OSM-Client für die Abfrage von OpenStreetMap-Daten.
"""

import osmnx as ox
import geopandas as gpd
from shapely.ops import transform
from pyproj import Transformer
import logging
from typing import Dict, Any, Optional
from .config import OSMConfig

logger = logging.getLogger(__name__)

class OSMBaseClient:
    """Basisklasse für OSM-Abfragen."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den OSM-Client.
        
        Args:
            config: Optionales Konfigurationsobjekt
        """
        self.config = OSMConfig(config)
        
    def fetch_buildings(self, site_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Ruft Gebäude von OpenStreetMap ab.
        
        Args:
            site_gdf: GeoDataFrame mit Site-Polygon
            
        Returns:
            GeoDataFrame mit Gebäuden
        """
        try:
            logger.info("🔄 Hole Gebäude von OSM")
            
            if site_gdf.empty:
                logger.error("⚠️ Leeres site_gdf übergeben")
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
                
            # Erstelle Buffer für Suche
            buffer_distance = self.config.buffer_distance
            site_polygon = site_gdf.geometry.iloc[0]
            search_area = site_polygon.buffer(buffer_distance)
            search_gdf = gpd.GeoDataFrame(geometry=[search_area], crs=site_gdf.crs)
            search_wgs84 = search_gdf.to_crs("EPSG:4326")
            
            # OSM-Abfrage
            buildings_gdf = ox.geometries_from_polygon(
                search_wgs84.geometry.iloc[0],
                tags={'building': True}
            )
            
            if buildings_gdf.empty:
                logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
                return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)
                
            # Konvertiere zum ursprünglichen CRS
            buildings_gdf = buildings_gdf.to_crs(site_gdf.crs)
            
            # Filtere Gebäude
            buildings_gdf = buildings_gdf[
                ~buildings_gdf.geometry.intersects(site_polygon) &
                buildings_gdf.geometry.intersects(search_area)
            ]
            
            logger.info(f"✅ OSM-Gebäude gefunden: {len(buildings_gdf)}")
            return buildings_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)
            
    def fetch_streets(self, site_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Ruft Straßen von OpenStreetMap ab.
        
        Args:
            site_gdf: GeoDataFrame mit Site-Polygon
            
        Returns:
            GeoDataFrame mit Straßen
        """
        try:
            logger.info("🔄 Hole Straßen von OSM")
            
            if site_gdf.empty:
                logger.error("⚠️ Leeres site_gdf übergeben")
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
                
            # Erstelle custom_filter aus der Konfiguration
            street_types = self.config.street_types
            street_type_list = list(street_types.keys()) if street_types else []
            street_types_str = '|'.join(street_type_list) if street_type_list else 'primary|secondary|tertiary|residential'
            custom_filter = f'["highway"~"{street_types_str}"]'
            
            # Konvertiere zu WGS84 für OSM-Abfrage
            site_wgs84 = site_gdf.to_crs("EPSG:4326")
            site_polygon_wgs = site_wgs84.geometry.iloc[0]
            
            # Hole Straßennetz
            G = ox.graph_from_polygon(
                site_polygon_wgs,
                network_type=self.config.network_type,
                custom_filter=custom_filter,
                retain_all=True,
                truncate_by_edge=True
            )
            
            # Konvertiere zu GeoDataFrame
            edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
            
            if edges.empty:
                logger.warning("⚠️ Keine OSM-Straßen gefunden!")
                return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)
                
            # Konvertiere zurück zum ursprünglichen CRS
            edges = edges.to_crs(site_gdf.crs)
            
            logger.info(f"✅ OSM-Straßen gefunden: {len(edges)}")
            return edges
            
        except Exception as e:
            logger.error(f"❌ Fehler beim OSM-Straßen Abruf: {str(e)}")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs) 
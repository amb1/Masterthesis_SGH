"""
OSM-Fetcher für die Verarbeitung von OSM-Daten.
"""

import geopandas as gpd
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

from .osm.client import OSMBaseClient
from .osm.geometry import OSMGeometryProcessor
from .osm.attributes import OSMAttributeProcessor
from .osm.config import OSMConfig

logger = logging.getLogger(__name__)

class OSMFetcher:
    """Hauptklasse für OSM-Datenverarbeitung."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den OSM-Fetcher.
        
        Args:
            config: Optionales Konfigurationsobjekt
        """
        self.config = OSMConfig(config)
        self.client = OSMBaseClient(config)
        self.geometry_processor = OSMGeometryProcessor()
        self.attribute_processor = OSMAttributeProcessor(config)
        
    def fetch_buildings(self, site_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Lädt OSM-Gebäude im Umkreis des Standorts.
        
        Args:
            site_gdf: GeoDataFrame mit Site-Polygon
            
        Returns:
            GeoDataFrame mit OSM-Gebäuden
        """
        try:
            logger.info("🔍 Hole OSM-Gebäude")
            
            # Hole Rohdaten von OSM
            buildings_gdf = self.client.fetch_buildings(site_gdf)
            
            if buildings_gdf.empty:
                logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
                return gpd.GeoDataFrame(
                    columns=['Name', 'height_ag', 'floors_ag', 'category', 'geometry', 'data_source'],
                    geometry='geometry',
                    crs=site_gdf.crs
                )
                
            # Verarbeite Gebäude
            processed_buildings = []
            for idx, building in buildings_gdf.iterrows():
                # Verarbeite Geometrie
                geometry = self.geometry_processor.process_building_geometry(building)
                if not geometry or not self.geometry_processor.validate_building_geometry(geometry):
                    logger.warning(f"⚠️ Ungültige Geometrie für Gebäude {idx}")
                    continue
                    
                # Verarbeite Attribute
                attributes = self.attribute_processor.process_building_attributes(building)
                if not attributes.get('Name'):
                    attributes['Name'] = f'OSM_{idx}'
                    
                # Füge Geometrie hinzu
                attributes['geometry'] = geometry
                processed_buildings.append(attributes)
                
            if not processed_buildings:
                logger.warning("⚠️ Keine gültigen Gebäude nach Verarbeitung!")
                return gpd.GeoDataFrame(
                    columns=['Name', 'height_ag', 'floors_ag', 'category', 'geometry', 'data_source'],
                    geometry='geometry',
                    crs=site_gdf.crs
                )
                
            # Erstelle GeoDataFrame
            result_gdf = gpd.GeoDataFrame(processed_buildings, crs=site_gdf.crs)
            logger.info(f"✅ OSM-Gebäude erfolgreich verarbeitet: {len(result_gdf)}")
            return result_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}")
            return gpd.GeoDataFrame(
                columns=['Name', 'height_ag', 'floors_ag', 'category', 'geometry', 'data_source'],
                geometry='geometry',
                crs=site_gdf.crs
            )
            
    def fetch_streets(self, site_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Lädt OSM-Straßen im Umkreis des Standorts.
        
        Args:
            site_gdf: GeoDataFrame mit Site-Polygon
            
        Returns:
            GeoDataFrame mit OSM-Straßen
        """
        try:
            logger.info("🔍 Hole OSM-Straßen")
            
            # Hole Rohdaten von OSM
            streets_gdf = self.client.fetch_streets(site_gdf)
            
            if streets_gdf.empty:
                logger.warning("⚠️ Keine OSM-Straßen gefunden!")
                return gpd.GeoDataFrame(
                    columns=['Name', 'width', 'lanes', 'surface', 'highway', 'geometry', 'data_source'],
                    geometry='geometry',
                    crs=site_gdf.crs
                )
                
            # Verarbeite Straßen
            processed_streets = []
            for idx, street in streets_gdf.iterrows():
                # Verarbeite Geometrie
                geometry = self.geometry_processor.process_street_geometry(street)
                if not geometry or not self.geometry_processor.validate_street_geometry(geometry):
                    logger.warning(f"⚠️ Ungültige Geometrie für Straße {idx}")
                    continue
                    
                # Verarbeite Attribute
                attributes = self.attribute_processor.process_street_attributes(street)
                if not attributes.get('Name'):
                    attributes['Name'] = f'OSM_STREET_{idx}'
                    
                # Füge Geometrie hinzu
                attributes['geometry'] = geometry
                processed_streets.append(attributes)
                
            if not processed_streets:
                logger.warning("⚠️ Keine gültigen Straßen nach Verarbeitung!")
                return gpd.GeoDataFrame(
                    columns=['Name', 'width', 'lanes', 'surface', 'highway', 'geometry', 'data_source'],
                    geometry='geometry',
                    crs=site_gdf.crs
                )
                
            # Erstelle GeoDataFrame
            result_gdf = gpd.GeoDataFrame(processed_streets, crs=site_gdf.crs)
            logger.info(f"✅ OSM-Straßen erfolgreich verarbeitet: {len(result_gdf)}")
            return result_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim OSM-Straßen Abruf: {str(e)}")
            return gpd.GeoDataFrame(
                columns=['Name', 'width', 'lanes', 'surface', 'highway', 'geometry', 'data_source'],
                geometry='geometry',
                crs=site_gdf.crs
            )
            
def fetch_osm_data(
    site_gdf: gpd.GeoDataFrame,
    data_type: str = 'buildings',
    config: Optional[Dict[str, Any]] = None
) -> gpd.GeoDataFrame:
    """
    Hilfsfunktion zum Abrufen von OSM-Daten.
    
    Args:
        site_gdf: GeoDataFrame mit Site-Polygon
        data_type: Art der Daten ('buildings' oder 'streets')
        config: Optionales Konfigurationsobjekt
        
    Returns:
        GeoDataFrame mit OSM-Daten
    """
    fetcher = OSMFetcher(config)
    
    if data_type == 'buildings':
        return fetcher.fetch_buildings(site_gdf)
    elif data_type == 'streets':
        return fetcher.fetch_streets(site_gdf)
    else:
        logger.error(f"❌ Ungültiger Datentyp: {data_type}")
        return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs) 
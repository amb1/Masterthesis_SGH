"""
OSM-Fetcher für die Verarbeitung von OSM-Daten.
"""

import geopandas as gpd
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from shapely.geometry import Polygon, MultiPolygon

from .osm.client import OSMClient
from .osm.geometry import OSMGeometry
from .osm.stream import OSMStream

logger = logging.getLogger(__name__)

def fetch_osm_buildings(
    polygon: Union[Polygon, MultiPolygon],
    output_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Lädt Gebäude von OpenStreetMap.
    
    Args:
        polygon: Polygon für die Abfrage
        output_dir: Optionaler Ausgabepfad
        config: Optionale Konfiguration
        
    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame mit Gebäuden
    """
    try:
        logger.info("🔄 Verarbeite OSM-Gebäude")
        
        # Initialisiere Komponenten
        client = OSMClient(config)
        geometry = OSMGeometry()
        stream = OSMStream()
        
        # Validiere Geometrie
        if not geometry.validate_geometry(polygon):
            logger.error("❌ Ungültiges Polygon")
            return None
            
        # Hole Gebäude von OSM
        buildings_data = client.get_buildings(polygon)
        if not buildings_data or not buildings_data.get('features'):
            logger.warning("⚠️ Keine OSM-Gebäude gefunden")
            return None
            
        # Konvertiere zu GeoDataFrame
        buildings_gdf = gpd.GeoDataFrame.from_features(
            buildings_data['features'],
            crs="EPSG:4326"
        )
        
        # Verarbeite Geometrien
        buildings_gdf.geometry = buildings_gdf.geometry.apply(
            lambda g: geometry.extract_footprint(g) if g else None
        )
        
        # Entferne ungültige Geometrien
        buildings_gdf = buildings_gdf[buildings_gdf.geometry.apply(
            lambda g: geometry.validate_geometry(g) if g else False
        )]
        
        if buildings_gdf.empty:
            logger.warning("⚠️ Keine gültigen Gebäude nach Verarbeitung")
            return None
            
        # Speichere Ergebnis
        if output_dir:
            output_path = Path(output_dir) / "buildings_osm.geojson"
            buildings_gdf.to_file(output_path, driver="GeoJSON")
            logger.info(f"✅ Gebäude gespeichert: {output_path}")
            
        return buildings_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der OSM-Gebäude Verarbeitung: {str(e)}")
        return None
        
def fetch_osm_streets(
    polygon: Union[Polygon, MultiPolygon],
    output_dir: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None
) -> Optional[gpd.GeoDataFrame]:
    """
    Lädt Straßen von OpenStreetMap.
    
    Args:
        polygon: Polygon für die Abfrage
        output_dir: Optionaler Ausgabepfad
        config: Optionale Konfiguration
        
    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame mit Straßen
    """
    try:
        logger.info("🔄 Verarbeite OSM-Straßen")
        
        # Initialisiere Komponenten
        client = OSMClient(config)
        geometry = OSMGeometry()
        stream = OSMStream()
        
        # Validiere Geometrie
        if not geometry.validate_geometry(polygon):
            logger.error("❌ Ungültiges Polygon")
            return None
            
        # Hole Straßen von OSM
        streets_data = client.get_streets(polygon)
        if not streets_data or not streets_data.get('features'):
            logger.warning("⚠️ Keine OSM-Straßen gefunden")
            return None
            
        # Konvertiere zu GeoDataFrame
        streets_gdf = gpd.GeoDataFrame.from_features(
            streets_data['features'],
            crs="EPSG:4326"
        )
        
        # Verarbeite Geometrien
        streets_gdf.geometry = streets_gdf.geometry.apply(
            lambda g: geometry.simplify_geometry(g) if g else None
        )
        
        # Entferne ungültige Geometrien
        streets_gdf = streets_gdf[streets_gdf.geometry.apply(
            lambda g: geometry.validate_geometry(g) if g else False
        )]
        
        if streets_gdf.empty:
            logger.warning("⚠️ Keine gültigen Straßen nach Verarbeitung")
            return None
            
        # Speichere Ergebnis
        if output_dir:
            output_path = Path(output_dir) / "streets_osm.geojson"
            streets_gdf.to_file(output_path, driver="GeoJSON")
            logger.info(f"✅ Straßen gespeichert: {output_path}")
            
        return streets_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der OSM-Straßen Verarbeitung: {str(e)}")
        return None 
"""
OSM-Street-Fetcher für die Verarbeitung von OSM-Straßendaten.
"""

import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from pyproj import Transformer
from pathlib import Path
import logging
import sys
import os
from shapely.geometry import LineString
from core.config_manager import load_config as load_yaml_config
from osmnx._errors import InsufficientResponseError
from typing import Dict, Any, Optional
from .osm.client import OSMBaseClient
from .osm.geometry import OSMGeometryProcessor
from .osm.attributes import OSMAttributeProcessor

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

logger = logging.getLogger(__name__)

def load_osm_config():
    """Lädt die OSM-Konfiguration für Straßen"""
    try:
        # Lade die konsolidierte OSM-Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        osm_config_path = root_dir / 'config' / 'osm' / 'config.yml'
        logger.info(f"📂 Lade OSM-Konfiguration: {osm_config_path}")

        osm_config = load_yaml_config(osm_config_path)
        if not osm_config:
            logger.error("❌ OSM-Konfiguration konnte nicht geladen werden")
            return None

        if not isinstance(osm_config, dict) or 'osm' not in osm_config:
            logger.warning("⚠️ Ungültige OSM-Konfiguration in config.yml")
            return None

        # Extrahiere die Straßen-Konfiguration
        streets_config = osm_config['osm'].get('streets', {})
        if not streets_config:
            logger.warning("⚠️ Keine Straßen-Konfiguration in config.yml gefunden")
            return None

        logger.info("✅ OSM-Straßen-Konfiguration erfolgreich geladen")
        return streets_config

    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        return None

def fetch_streets_within_site(site_gdf, config):
    """
    Ruft Straßen aus OSM innerhalb des Site-Polygons ab
    
    Args:
        site_gdf: GeoDataFrame oder MultiPolygon mit Site-Polygon
        config: Konfigurationsobjekt mit Straßeneinstellungen
    """
    logger.info("🔄 Hole Straßen von OSM")
    
    try:
        # Konvertiere zu GeoDataFrame wenn nötig
        if not isinstance(site_gdf, gpd.GeoDataFrame):
            logger.info("🔄 Konvertiere MultiPolygon zu GeoDataFrame")
            site_gdf = gpd.GeoDataFrame(geometry=[site_gdf], crs="EPSG:31256")
        
        # Stelle sicher, dass ein CRS vorhanden ist
        if not site_gdf.crs:
            logger.warning("⚠️ Kein CRS in site_gdf gefunden, setze EPSG:31256")
            site_gdf.set_crs(epsg=31256, inplace=True)
        
        # Erstelle custom_filter aus der Konfiguration
        street_types = config.get('street_types', {})
        street_type_list = list(street_types.keys()) if isinstance(street_types, dict) else []
        street_types_str = '|'.join(street_type_list) if street_type_list else 'primary|secondary|tertiary|residential'
        custom_filter = f'["highway"~"{street_types_str}"]'
        
        # Konvertiere zu WGS84 für OSM-Abfrage
        transformer = Transformer.from_crs(site_gdf.crs, "EPSG:4326", always_xy=True)
        site_polygon_wgs = transform(transformer.transform, site_gdf.geometry.iloc[0])
        
        # Hole Straßennetz von OSM mit Filter
        network_type = config.get('network_type', 'all')
        if network_type == 'all_private':
            custom_filter = '["highway"]'  # Alle highway-Tags
        
        G = ox.graph_from_polygon(
            site_polygon_wgs,
            network_type='all',  # Verwende 'all' für maximale Abdeckung
            custom_filter=custom_filter,
            retain_all=True,
            truncate_by_edge=True
        )
        
        # Konvertiere zu GeoDataFrame
        edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
        
        # Konvertiere zurück zum ursprünglichen CRS
        edges = edges.to_crs(site_gdf.crs)
        
        logger.info(f"✅ Anzahl gefundener Straßensegmente: {len(edges)}")
        logger.info("\nGefundene Straßentypen:")
        
        # Verarbeite die highway-Typen und handle Listen
        if 'highway' in edges.columns:
            highway_types = {}
            for highway in edges['highway']:
                # Wenn es eine Liste ist, nehme den ersten Typ
                if isinstance(highway, list):
                    highway = highway[0]
                highway_types[highway] = highway_types.get(highway, 0) + 1
            
            # Gib die Statistik aus
            for highway_type, count in highway_types.items():
                logger.info(f"- {highway_type}: {count} Segmente")
        
        # Verarbeite die Straßen
        edges = process_streets(edges)
        
        return edges
    except Exception as e:
        logger.error(f"❌ Fehler beim Abrufen der Straßen: {str(e)}")
        raise

def process_streets(edges_gdf):
    """
    Verarbeitet das Straßennetz und erstellt erforderliche Attribute
    
    Args:
        edges_gdf: GeoDataFrame mit Straßenkanten
    """
    logger.info("🔄 Verarbeite Straßennetz")
    
    if edges_gdf.empty:
        logger.info("✅ Straßennetz verarbeitet: 0 Segmente")
        # Erstelle leeres GeoDataFrame mit allen erforderlichen Spalten
        empty_gdf = gpd.GeoDataFrame(
            columns=['geometry', 'Name', 'width', 'lanes', 'surface', 'highway', 'data_source'],
            crs=edges_gdf.crs
        )
        return empty_gdf
    
    # Erstelle GeoDataFrame mit vorhandenen Attributen
    streets_data = []
    for _, edge in edges_gdf.iterrows():
        street_data = {
            'geometry': edge.geometry,
            'data_source': 'osm'
        }
        
        # Extrahiere nur vorhandene Attribute
        if 'name' in edge and edge['name']:
            street_data['Name'] = edge['name']
            
        if 'width' in edge and edge['width']:
            try:
                street_data['width'] = float(edge['width'])
            except (ValueError, TypeError):
                pass
                
        if 'lanes' in edge and edge['lanes']:
            try:
                street_data['lanes'] = int(edge['lanes'])
            except (ValueError, TypeError):
                pass
                
        if 'surface' in edge and edge['surface']:
            street_data['surface'] = edge['surface']
            
        if 'highway' in edge:
            highway = edge['highway']
            if isinstance(highway, list):
                highway = highway[0]
            street_data['highway'] = highway
            
        streets_data.append(street_data)
    
    streets_gdf = gpd.GeoDataFrame(streets_data, crs=edges_gdf.crs)
    logger.info(f"✅ Straßennetz verarbeitet: {len(streets_gdf)} Segmente")
    return streets_gdf

def save_streets(streets_gdf, output_path):
    """Speichert das Straßennetz als Shapefile"""
    print(f"Speichere Straßennetz nach: {output_path}")
    
    # Stelle sicher, dass der Ausgabeordner existiert
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    streets_gdf.to_file(output_path, driver='ESRI Shapefile')
    print("Straßennetz erfolgreich gespeichert")

def fetch_osm_streets(site_gdf: gpd.GeoDataFrame, config: Optional[Dict[str, Any]] = None) -> gpd.GeoDataFrame:
    """
    Lädt Straßen von OpenStreetMap.
    
    Args:
        site_gdf: GeoDataFrame mit Site-Polygon
        config: Optionales Konfigurationsobjekt
        
    Returns:
        GeoDataFrame mit OSM-Straßen
    """
    try:
        logger.info("🔍 Hole OSM-Straßen")
        
        # Initialisiere Komponenten
        client = OSMBaseClient(config)
        geometry_processor = OSMGeometryProcessor()
        attribute_processor = OSMAttributeProcessor(config)
        
        # Hole Rohdaten von OSM
        streets_gdf = client.fetch_streets(site_gdf)
        
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
            geometry = geometry_processor.process_street_geometry(street)
            if not geometry or not geometry_processor.validate_street_geometry(geometry):
                logger.warning(f"⚠️ Ungültige Geometrie für Straße {idx}")
                continue
                
            # Verarbeite Attribute
            attributes = attribute_processor.process_street_attributes(street)
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

def main():
    try:
        logger.info("🚀 Starte OSM-Straßen Abruf...")
        config = load_osm_config()
        if not config:
            raise ValueError("❌ Keine gültige Konfiguration gefunden")
            
        # Lade globale Konfiguration für Pfade
        root_dir = Path(__file__).resolve().parent.parent.parent
        global_config = load_yaml_config(root_dir / 'config' / 'global.yml')
        if not global_config:
            raise ValueError("❌ Keine gültige globale Konfiguration gefunden")
            
        # Erstelle Pfade
        paths = global_config.get('paths', {})
        geometry_path = Path(paths.get('outputs', {}).get('geometry', 'outputs/geometry'))
        networks_path = Path(paths.get('outputs', {}).get('networks', 'outputs/networks'))
        
        # Stelle sicher, dass die Ausgabeverzeichnisse existieren
        geometry_path.mkdir(parents=True, exist_ok=True)
        networks_path.mkdir(parents=True, exist_ok=True)
        
        # Lade Site-Polygon
        site_path = geometry_path / 'site.shp'
        if not site_path.exists():
            raise FileNotFoundError(f"❌ site.shp nicht gefunden in {site_path}")
        
        site_gdf = gpd.read_file(site_path)
        if not site_gdf.crs:
            logger.warning("⚠️ Kein CRS in site.shp gefunden, setze EPSG:31256")
            site_gdf.set_crs(epsg=31256, inplace=True)
        
        # Hole OSM-Straßen mit der importierten Funktion
        streets = fetch_osm_streets(site_gdf, config)
        
        if streets.empty:
            logger.warning("⚠️ Keine Straßen gefunden!")
            return
            
        # Verarbeite Straßen
        processed_streets = process_streets(streets)
        
        # Speichere Straßen
        save_streets(processed_streets, networks_path / 'streets.shp')
        
        logger.info("✅ OSM-Straßen Abruf erfolgreich abgeschlossen!")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Straßen Abruf: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main() 
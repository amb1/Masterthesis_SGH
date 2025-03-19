import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from pyproj import Transformer
from pathlib import Path
import logging
import sys
import os

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.config_loader import load_config as load_yaml_config

logger = logging.getLogger(__name__)

def load_osm_config():
    """Lädt die Projekt-Konfiguration für OSM-Straßen"""
    try:
        # Lade zuerst die Projekt-Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        project_config_path = root_dir / 'cfg' / 'project_config.yml'
        logger.info(f"📂 Lade Projekt-Konfiguration: {project_config_path}")

        project_config = load_yaml_config(project_config_path)
        if not project_config:
            logger.error("❌ Projekt-Konfiguration konnte nicht geladen werden")
            return None

        # Hole OSM-Konfigurationspfad aus project_config
        osm_config_path = project_config.get('project', {}).get('config_files', {}).get('osm', {}).get('config')
        
        if not osm_config_path:
            logger.warning("⚠️ Kein OSM-Konfigurationspfad in project/config_files/osm/config gefunden")
            return None

        # Stelle sicher, dass der Pfad nicht doppelt 'local/' enthält
        osm_config_path = Path(osm_config_path)

        # Falls der Pfad mit 'local/' beginnt, entferne es
        if osm_config_path.parts[0] == 'local':
            osm_config_path = osm_config_path.relative_to('local')

        # Konstruiere absoluten Pfad basierend auf root_dir
        osm_config_path = root_dir / osm_config_path
        
        logger.info(f"📂 Lade OSM-Konfiguration: {osm_config_path}")

        # Lade die OSM-Konfiguration
        osm_config = load_yaml_config(osm_config_path)
        if not osm_config:
            logger.error("❌ OSM-Konfiguration konnte nicht geladen werden")
            return None

        if not isinstance(osm_config, dict) or 'osm' not in osm_config:
            logger.warning("⚠️ Ungültige OSM-Konfiguration in osm_config.yml")
            return None

        # Extrahiere die Straßen-Konfiguration
        streets_config = osm_config['osm'].get('streets', {})
        if not streets_config:
            logger.warning("⚠️ Keine Straßen-Konfiguration in osm_config.yml gefunden")
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
    
    return edges

def process_streets(edges_gdf):
    """
    Verarbeitet das Straßennetz und erstellt erforderliche Attribute
    """
    print("Verarbeite Straßennetz")
    
    # Erstelle GeoDataFrame mit benötigten Spalten
    streets_gdf = gpd.GeoDataFrame(
        {
            'u': edges_gdf.apply(lambda x: f"{x.geometry.coords[0][0]:.2f},{x.geometry.coords[0][1]:.2f}", axis=1),
            'v': edges_gdf.apply(lambda x: f"{x.geometry.coords[-1][0]:.2f},{x.geometry.coords[-1][1]:.2f}", axis=1),
            'key': range(len(edges_gdf))
        },
        geometry=edges_gdf.geometry,
        crs=edges_gdf.crs
    )
    
    # Setze den Index zurück, falls einer existiert
    streets_gdf = streets_gdf.reset_index(drop=True)
    
    print(f"Straßennetz verarbeitet: {len(streets_gdf)} Segmente")
    return streets_gdf

def save_streets(streets_gdf, output_path):
    """Speichert das Straßennetz als Shapefile"""
    print(f"Speichere Straßennetz nach: {output_path}")
    
    # Stelle sicher, dass der Ausgabeordner existiert
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    streets_gdf.to_file(output_path, driver='ESRI Shapefile')
    print("Straßennetz erfolgreich gespeichert")

def fetch_osm_streets(site_polygon, config: dict) -> gpd.GeoDataFrame:
    """Holt Straßendaten aus OpenStreetMap"""
    try:
        # Stelle sicher, dass config ein Dictionary ist
        if not isinstance(config, dict):
            logger.warning("⚠️ Konfiguration ist kein Dictionary, verwende Standardwerte")
            config = {
                'buffer_distance': 100,
                'street_types': {
                    'primary': True,
                    'secondary': True,
                    'tertiary': True,
                    'residential': True,
                    'service': True,
                    'living_street': True,
                    'pedestrian': True,
                    'footway': True,
                    'cycleway': True
                }
            }
        
        # Extrahiere Konfigurationswerte
        buffer_distance = config.get('buffer_distance', 100)
        street_types = config.get('street_types', {})
        
        logger.info(f"📡 OSM-Abfrage: Straßen im Umkreis von {buffer_distance}m")
        
        # Konvertiere MultiPolygon zu GeoDataFrame wenn nötig
        if not isinstance(site_polygon, gpd.GeoDataFrame):
            logger.info("🔄 Konvertiere MultiPolygon zu GeoDataFrame")
            site_polygon = gpd.GeoDataFrame(geometry=[site_polygon], crs="EPSG:31256")
        
        # Stelle sicher, dass site_polygon ein gültiges CRS hat
        if not site_polygon.crs:
            logger.warning("⚠️ Kein CRS in site_polygon gefunden, setze EPSG:31256")
            site_polygon.set_crs(epsg=31256, inplace=True)
        
        # Erstelle Buffer für Suche
        search_area = site_polygon.geometry.buffer(buffer_distance).unary_union
        search_gdf = gpd.GeoDataFrame(geometry=[search_area], crs=site_polygon.crs)
        search_wgs84 = search_gdf.to_crs("EPSG:4326")
        
        # Erstelle custom_filter für OSM-Abfrage
        street_type_list = [k for k, v in street_types.items() if v]
        if not street_type_list:
            street_type_list = ['primary', 'secondary', 'tertiary', 'residential']
        street_types_str = '|'.join(street_type_list)
        custom_filter = f'["highway"~"{street_types_str}"]'
        
        logger.info(f"🔍 Suche nach Straßentypen: {street_types_str}")
        
        # Hole Straßen von OSM
        G = ox.graph_from_polygon(
            search_wgs84.geometry.iloc[0],
            network_type='all',
            custom_filter=custom_filter,
            retain_all=True,
            truncate_by_edge=True
        )
        
        # Konvertiere zu GeoDataFrame
        streets_gdf = ox.graph_to_gdfs(G, nodes=False, edges=True)
        
        if streets_gdf.empty:
            logger.warning("⚠️ Keine OSM-Straßen gefunden!")
            return gpd.GeoDataFrame(geometry=[], crs=site_polygon.crs)
            
        # Konvertiere zum ursprünglichen CRS
        streets_gdf = streets_gdf.to_crs(site_polygon.crs)
        
        # Filtere Straßen im Suchbereich
        streets_gdf = streets_gdf[streets_gdf.geometry.intersects(search_area)]
        
        logger.info(f"✅ OSM-Straßen gefunden: {len(streets_gdf)}")
        return streets_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Straßen Abruf: {str(e)}")
        return gpd.GeoDataFrame(geometry=[], crs=site_polygon.crs)

def main():
    try:
        logger.info("🚀 Starte OSM-Straßen Abruf...")
        config = load_osm_config()
        if not config:
            raise ValueError("❌ Keine gültige Projekt-Konfiguration gefunden")
            
        # Erstelle Pfade
        geometry_path = Path(config.get('paths', {}).get('geometry', 'outputs/geometry'))
        networks_path = Path(config.get('paths', {}).get('networks', 'outputs/networks'))
        
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
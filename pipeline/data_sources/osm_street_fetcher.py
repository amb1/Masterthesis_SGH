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

def process_streets(edges_gdf, defaults=None):
    """
    Verarbeitet das Straßennetz und erstellt erforderliche Attribute
    
    Args:
        edges_gdf: GeoDataFrame mit Straßenkanten
        defaults: Dictionary mit Standardwerten für fehlende Attribute
    """
    logger.info("🔄 Verarbeite Straßennetz")
    
    if edges_gdf.empty:
        logger.info("✅ Straßennetz verarbeitet: 0 Segmente")
        # Erstelle leeres GeoDataFrame mit allen erforderlichen Spalten
        empty_gdf = gpd.GeoDataFrame(
            columns=['geometry', 'Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'],
            crs=edges_gdf.crs
        )
        return empty_gdf
    
    # Setze Standardwerte wenn nicht übergeben
    if defaults is None:
        defaults = {
            'width': 3.0,
            'lanes': 2,
            'surface': 'asphalt',
            'REFERENCE': ''
        }
    
    # Erstelle GeoDataFrame mit benötigten Spalten
    streets_gdf = gpd.GeoDataFrame(
        {
            'Name': edges_gdf.get('name', ''),
            'width': edges_gdf.get('width', defaults.get('width', 3.0)),
            'lanes': edges_gdf.get('lanes', defaults.get('lanes', 2)),
            'surface': edges_gdf.get('surface', defaults.get('surface', 'asphalt')),
            'highway': edges_gdf.get('highway', ''),
            'REFERENCE': edges_gdf.get('ref', defaults.get('REFERENCE', '')),
            'geometry': edges_gdf.geometry
        },
        crs=edges_gdf.crs
    )
    
    # Konvertiere Listen zu einzelnen Werten
    if 'highway' in streets_gdf.columns:
        streets_gdf['highway'] = streets_gdf['highway'].apply(
            lambda x: x[0] if isinstance(x, list) else x
        )
    
    logger.info(f"✅ Straßennetz verarbeitet: {len(streets_gdf)} Segmente")
    return streets_gdf

def save_streets(streets_gdf, output_path):
    """Speichert das Straßennetz als Shapefile"""
    print(f"Speichere Straßennetz nach: {output_path}")
    
    # Stelle sicher, dass der Ausgabeordner existiert
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    streets_gdf.to_file(output_path, driver='ESRI Shapefile')
    print("Straßennetz erfolgreich gespeichert")

def fetch_osm_streets(site_polygon, config):
    """
    Ruft Straßen von OpenStreetMap ab
    
    Args:
        site_polygon: GeoDataFrame oder MultiPolygon mit Suchbereich
        config: Konfigurationsobjekt mit Straßeneinstellungen
    """
    try:
        # Setze Standardkonfiguration wenn keine übergeben wurde
        if not isinstance(config, dict):
            logger.warning("⚠️ Konfiguration ist kein Dictionary, verwende Standardwerte")
            config = {
                'tags': {
                    'highway': ['primary', 'secondary', 'tertiary', 'residential']
                },
                'defaults': {
                    'width': 3.0,
                    'lanes': 2,
                    'surface': 'asphalt',
                    'REFERENCE': ''
                }
            }
        
        # Extrahiere Konfigurationswerte
        tags = config.get('tags', {})
        defaults = config.get('defaults', {})
        street_types = tags.get('highway', ['primary', 'secondary', 'tertiary', 'residential'])
        
        logger.info(f"📡 OSM-Abfrage: Straßen mit Typen {street_types}")
        
        # Konvertiere MultiPolygon zu GeoDataFrame wenn nötig
        if not isinstance(site_polygon, gpd.GeoDataFrame):
            logger.info("🔄 Konvertiere MultiPolygon zu GeoDataFrame")
            site_polygon = gpd.GeoDataFrame(geometry=[site_polygon], crs="EPSG:31256")
        
        # Stelle sicher, dass site_polygon ein gültiges CRS hat
        if not site_polygon.crs:
            logger.warning("⚠️ Kein CRS in site_polygon gefunden, setze EPSG:31256")
            site_polygon.set_crs(epsg=31256, inplace=True)
        
        # Erstelle custom_filter für OSM-Abfrage
        street_types_str = '|'.join(street_types)
        custom_filter = f'["highway"~"{street_types_str}"]'
        
        logger.info(f"🔍 Suche nach Straßentypen: {street_types_str}")
        
        # Konvertiere zu WGS84 für OSM-Abfrage
        search_wgs84 = site_polygon.to_crs("EPSG:4326")
        
        try:
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
                empty_gdf = gpd.GeoDataFrame(
                    columns=['geometry', 'Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'],
                    crs="EPSG:31256"
                )
                return empty_gdf
                
            # Konvertiere zum ursprünglichen CRS
            streets_gdf = streets_gdf.to_crs(site_polygon.crs)
            
            # Filtere Straßen im Suchbereich
            streets_gdf = streets_gdf[streets_gdf.geometry.intersects(site_polygon.geometry.iloc[0])]
            
            # Verarbeite die Straßen mit den Standardwerten
            streets_gdf = process_streets(streets_gdf, defaults)
            
            logger.info(f"✅ OSM-Straßen gefunden: {len(streets_gdf)}")
            return streets_gdf
            
        except InsufficientResponseError as e:
            logger.warning("⚠️ Keine OSM-Straßen gefunden!")
            empty_gdf = gpd.GeoDataFrame(
                columns=['geometry', 'Name', 'width', 'lanes', 'surface', 'highway', 'REFERENCE'],
                crs="EPSG:31256"
            )
            return empty_gdf
            
    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Straßen Abruf: {str(e)}")
        raise

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
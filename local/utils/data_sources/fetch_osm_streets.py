import osmnx as ox
import geopandas as gpd
import pandas as pd
from shapely.ops import transform
from pyproj import Transformer
from pathlib import Path
import yaml

def fetch_streets_within_site(site_gdf, config):
    """
    Ruft Straßen aus OSM innerhalb des Site-Polygons ab
    
    Args:
        site_gdf: GeoDataFrame mit Site-Polygon
        config: Konfigurationsobjekt mit Straßeneinstellungen
    """
    print("Hole Straßen von OSM")
    
    # Erstelle custom_filter aus der Konfiguration
    street_types = '|'.join(config['streets']['include_types'])
    custom_filter = f'["highway"~"{street_types}"]'
    
    # Konvertiere zu WGS84 für OSM-Abfrage
    transformer = Transformer.from_crs(site_gdf.crs, "EPSG:4326", always_xy=True)
    site_polygon_wgs = transform(transformer.transform, site_gdf.geometry.iloc[0])
    
    # Hole Straßennetz von OSM mit Filter
    if config['streets']['network_type'] == 'all_private':
        # Spezielle Behandlung für all_private
        custom_filter = '["highway"]'  # Alle highway-Tags
    
    G = ox.graph_from_polygon(
        site_polygon_wgs,
        network_type='all',  # Verwende 'all' für maximale Abdeckung
        custom_filter=custom_filter,
        retain_all=config['streets']['retain_all'],
        truncate_by_edge=config['streets']['truncate_by_edge']
    )
    
    # Konvertiere zu GeoDataFrame
    edges = ox.graph_to_gdfs(G, nodes=False, edges=True)
    
    # Konvertiere zurück zum ursprünglichen CRS
    edges = edges.to_crs(site_gdf.crs)
    
    print(f"Anzahl gefundener Straßensegmente: {len(edges)}")
    print("\nGefundene Straßentypen:")
    
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
            print(f"- {highway_type}: {count} Segmente")
    
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

def load_config():
    """Lädt die OSM-Straßen Konfiguration"""
    try:
        # Absoluter Pfad zur Konfigurationsdatei
        config_path = Path(__file__).resolve().parent.parent.parent / 'cfg' / 'data_sources' / 'osm_config.yml'
        print(f"Lade OSM Konfiguration: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        return config.get('streets', {})
        
    except Exception as e:
        print(f"Fehler beim Laden der OSM Konfiguration: {str(e)}")
        return None

def fetch_osm_streets(site_polygon, street_types=None):
    """Lädt OSM-Straßendaten für den gegebenen Bereich"""
    try:
        print("Hole OSM-Straßen")
        
        streets_df = gpd.GeoDataFrame(geometry=[], crs=site_polygon.crs)
        
        if site_polygon is None or site_polygon.empty:
            print("❌ Fehler: Kein gültiges Site-Polygon")
            return streets_df
        
        # Konvertiere zu WGS84 für OSM
        site_wgs84 = site_polygon.to_crs("EPSG:4326")
        
        # Hole Straßen von OSM
        try:
            streets = ox.features_from_polygon(
                site_wgs84.geometry.iloc[0],
                tags={'highway': True}
            )
            
            if not streets.empty:
                # Konvertiere zurück zum ursprünglichen CRS
                streets_df = streets.to_crs(site_polygon.crs)
                print(f"✅ {len(streets_df)} Straßen geladen")
            else:
                print("⚠️ Keine Straßen gefunden")
                
        except Exception as e:
            print(f"Fehler beim OSM-Straßen Abruf: {str(e)}")
            
        return streets_df
        
    except Exception as e:
        print(f"Fehler beim OSM-Straßen Abruf: {str(e)}")
        return gpd.GeoDataFrame(geometry=[], crs=site_polygon.crs)

def main():
    try:
        print("Starte OSM-Straßen Abruf...")
        config = load_config()
        if not config:
            raise ValueError("Keine gültige OSM Konfiguration gefunden")
            
        # Weitere Verarbeitung...
        
        # Lade Konfiguration
        config = load_config()
        print("Konfiguration geladen")
        
        # Erstelle Pfade
        geometry_path = Path(config['paths']['output']['geometry'])
        networks_path = Path(config['paths']['output']['networks'])
        
        # Lade Site-Polygon
        site_path = geometry_path / 'site.shp'
        if not site_path.exists():
            raise FileNotFoundError(f"site.shp nicht gefunden in {site_path}")
        
        site_gdf = gpd.read_file(site_path)
        
        # Hole OSM-Straßen
        streets = fetch_streets_within_site(site_gdf, config)
        
        # Verarbeite Straßen
        processed_streets = process_streets(streets)
        
        # Speichere Straßen
        save_streets(processed_streets, networks_path / 'streets.shp')
        
        print("OSM-Straßen Abruf erfolgreich abgeschlossen!")
        
    except Exception as e:
        print(f"Fehler beim OSM-Straßen Abruf: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
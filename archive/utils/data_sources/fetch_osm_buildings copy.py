import osmnx as ox
import geopandas as gpd
from shapely.ops import unary_union
from pathlib import Path
import yaml
import logging
import sys
import os
import overpy
from shapely.geometry import Polygon
from pyproj import Transformer
from pyproj import transform
import pandas as pd
from shapely.geometry import box
import numpy as np
from packaging import version

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.config_loader import load_config

logger = logging.getLogger(__name__)

# Prüfe osmnx Version
ox_version = version.parse(ox.__version__)

# Passe Overpass-Einstellungen an
ox.settings.overpass_max_query_area_size = 100_000_000  # Verdoppele die maximale Abfragegröße
ox.settings.timeout = 180  # Erhöhe Timeout auf 3 Minuten für größere Abfragen

def fetch_surrounding_buildings(site_gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """Holt Gebäude aus OpenStreetMap im Umkreis des Standorts."""
    try:
        if site_gdf is None or site_gdf.empty:
            logger.error("⚠️ Ungültiges oder leeres site_gdf übergeben")
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

        # Hole Konfigurationswerte
        buffer_distance = min(config.get('buildings', {}).get('buffer_distance', 100), 500)  # Begrenze auf 500m
        building_defaults = config.get('buildings', {}).get('defaults', {
            'height': 10,
            'floors': 3,
            'year': 1990
        })

        logger.info(f"📡 OSM-Abfrage: Gebäude im Umkreis von {buffer_distance}m")

        # Speichere ursprüngliches CRS
        original_crs = site_gdf.crs if site_gdf.crs else "EPSG:31256"

        # Stelle sicher, dass ein CRS vorhanden ist
        if not site_gdf.crs:
            site_gdf.set_crs(epsg=31256, inplace=True)

        # Erstelle Buffer für Suche
        site_polygon = site_gdf.geometry.iloc[0]
        search_area = site_polygon.buffer(buffer_distance)
        search_gdf = gpd.GeoDataFrame(geometry=[search_area], crs=site_gdf.crs)
        search_wgs84 = search_gdf.to_crs("EPSG:4326")
        
        # Extrahiere BBox für OSM-Abfrage
        minx, miny, maxx, maxy = search_wgs84.total_bounds
        logger.info(f"🗺️ BBox für OSM-Abfrage: N={maxy}, S={miny}, E={maxx}, W={minx}")
        
        # Hole OSM-Gebäude
        buildings_gdf = fetch_osm_buildings((minx, miny, maxx, maxy), config)

        if buildings_gdf.empty:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return gpd.GeoDataFrame(
                columns=['Name', 'height_ag', 'floors_ag', 'category', 'REFERENCE', 'geometry'],
                geometry='geometry',
                crs=original_crs
            )

        # Konvertiere zum ursprünglichen CRS
        buildings_gdf = buildings_gdf.to_crs(original_crs)

        # Filtere Gebäude: Nur die, die außerhalb des site_polygon aber innerhalb des Suchbereichs liegen
        buildings_gdf = buildings_gdf[
            ~buildings_gdf.geometry.intersects(site_polygon) &  # Nicht im site_polygon
            buildings_gdf.geometry.intersects(search_area)      # Im Suchbereich
        ]

        if buildings_gdf.empty:
            logger.warning("⚠️ Keine gültigen Gebäude gefunden!")
            return gpd.GeoDataFrame(
                columns=['Name', 'height_ag', 'floors_ag', 'category', 'REFERENCE', 'geometry'],
                geometry='geometry',
                crs=original_crs
            )

        logger.info(f"✅ OSM-Gebäude gefunden: {len(buildings_gdf)}")
        return buildings_gdf

    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}")
        return gpd.GeoDataFrame(
            columns=['Name', 'height_ag', 'floors_ag', 'category', 'REFERENCE', 'geometry'],
            geometry='geometry',
            crs=original_crs if 'original_crs' in locals() else "EPSG:4326"
        )

def process_osm_buildings(buildings_gdf, osm_defaults):
    """
    Verarbeitet OSM-Gebäude und erstellt erforderliche Attribute
    """
    logger.info("🔄 Verarbeite OSM-Gebäude")

    if buildings_gdf.empty:
        logger.warning("⚠️ Keine OSM-Gebäude zu verarbeiten!")
        return gpd.GeoDataFrame(geometry=[], crs=buildings_gdf.crs)

    processed_rows = []
    for i, row in buildings_gdf.iterrows():
        if not hasattr(row.geometry, 'exterior'):
            logger.warning(f"⚠️ Gebäude {i} übersprungen: Keine Polygon-Geometrie")
            continue

        floors = row.get('building:levels', osm_defaults.get('default_floors', 3))
        try:
            floors = int(floors)
        except (ValueError, TypeError):
            floors = osm_defaults.get('default_floors', 3)

        processed_rows.append({
            'Name': f'OSM_{i}',
            'height_ag': floors * osm_defaults.get('floor_height', 3),
            'floors_ag': floors,
            'category': osm_defaults.get('category', 'residential'),
            'REFERENCE': osm_defaults.get('REFERENCE', ''),
            'geometry': row.geometry
        })

    processed_gdf = gpd.GeoDataFrame(processed_rows, crs=buildings_gdf.crs)
    logger.info(f"✅ OSM-Gebäude verarbeitet: {len(processed_gdf)} Gebäude")
    return processed_gdf

def save_surrounding_buildings(buildings_gdf, output_path):
    """Speichert die Umgebungsgebäude als Shapefile"""
    try:
        logger.info(f"💾 Speichere OSM-Gebäude nach: {output_path}")
        buildings_gdf.to_file(output_path, driver='ESRI Shapefile')
        logger.info("✅ Umgebungsgebäude erfolgreich gespeichert")
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der OSM-Gebäude: {str(e)}", exc_info=True)

def fetch_osm_buildings(bbox, config):
    """Holt Gebäudedaten von OpenStreetMap"""
    try:
        logger.info(f"🔍 Hole OSM-Gebäude mit {config}")
        
        # Validiere bbox Parameter
        if not isinstance(bbox, (tuple, list, np.ndarray)) or len(bbox) != 4:
            raise ValueError("❌ bbox muss ein Tupel oder Liste mit 4 Werten sein (minx, miny, maxx, maxy)")
            
        # Extrahiere BBox-Koordinaten
        minx, miny, maxx, maxy = bbox
        
        # Konvertiere zu OSM-Format (north, south, east, west)
        north = maxy  # max latitude
        south = miny  # min latitude
        east = maxx   # max longitude
        west = minx   # min longitude
        
        # Hole Tags aus der Konfiguration oder verwende Default
        tags = config.get('osm', {}).get('tags', {}).get('buildings', {'building': True})
        if isinstance(tags, list):
            tags = {'building': True}  # Fallback wenn tags eine Liste ist
        
        # Hole OSM-Gebäude entsprechend der osmnx Version
        if ox_version >= version.parse("1.3.0"):
            raw_result = ox.features_from_bbox(
                north, south, east, west,  # Direkte Übergabe der Koordinaten
                tags=tags
            )
        else:
            raw_result = ox.features_from_bbox(
                north,  # max latitude
                south,  # min latitude
                east,   # max longitude
                west,   # min longitude
                tags
            )
        
        # Sicherheitscheck für Rückgabetyp
        if not isinstance(raw_result, gpd.GeoDataFrame):
            logger.warning("⚠️ OSM-Antwort ist kein GeoDataFrame – vermutlich leer oder fehlerhaft")
            return gpd.GeoDataFrame(
                columns=['Name', 'height_ag', 'floors_ag', 'category', 'REFERENCE', 'geometry'],
                geometry='geometry',
                crs="EPSG:4326"
            )
            
        buildings_gdf = raw_result
        
        # Validiere Geometrien
        valid_mask = buildings_gdf.geometry.apply(lambda geom: geom.is_valid and hasattr(geom, 'exterior'))
        if not valid_mask.all():
            logger.warning(f"⚠️ {(~valid_mask).sum()} ungültige Geometrien gefunden und entfernt")
            buildings_gdf = buildings_gdf[valid_mask]
        
        # Verarbeite die Gebäude
        if not buildings_gdf.empty:
            # Verarbeite die Gebäude mit den Standardwerten aus der Konfiguration
            buildings_gdf = process_osm_buildings(buildings_gdf, config.get('osm', {}).get('buildings', {}).get('defaults', {}))
            logger.info(f"✅ {len(buildings_gdf)} OSM-Gebäude gefunden")
            return buildings_gdf
            
        logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}")
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

def main():
    try:
        logger.info("🚀 Starte OSM-Gebäude Abruf...")
        
        # Lade Projekt-Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        project_config_path = root_dir / 'cfg' / 'project_config.yml'
        logger.info(f"📂 Lade Projekt-Konfiguration: {project_config_path}")
        project_config = load_config(project_config_path)
        
        if not project_config:
            raise ValueError("❌ Keine gültige Projekt-Konfiguration gefunden")

        # Hole OSM-Konfigurationspfad aus project_config
        osm_config_path = project_config.get('project', {}).get('config_files', {}).get('osm', {}).get('config')
        
        if not osm_config_path:
            raise ValueError("❌ Kein OSM-Konfigurationspfad in project/config_files/osm/config gefunden")

        # Stelle sicher, dass der Pfad nicht doppelt 'local/' enthält
        osm_config_path = Path(osm_config_path)

        # Falls der Pfad mit 'local/' beginnt, entferne es
        if osm_config_path.parts[0] == 'local':
            osm_config_path = osm_config_path.relative_to('local')

        # Konstruiere absoluten Pfad basierend auf root_dir
        osm_config_path = root_dir / osm_config_path
        
        logger.info(f"📂 Lade OSM-Konfiguration: {osm_config_path}")
        osm_config = load_config(osm_config_path)

        if not osm_config:
            raise ValueError("❌ Keine gültige OSM-Konfiguration gefunden")

        # Hole Pfade aus der Projekt-Konfiguration
        paths = project_config.get('project', {}).get('paths', {})
        if not paths:
            raise ValueError("❌ Keine Pfade in der Projekt-Konfiguration gefunden")

        # Setze Pfade für Geometrie und Output
        geometry_path = Path(paths['outputs']['buildings'])
        site_path = geometry_path / 'site.shp'

        if not site_path.exists():
            raise FileNotFoundError(f"❌ site.shp nicht gefunden in {site_path}")

        # Hole Building-Defaults aus der OSM-Konfiguration
        building_defaults = osm_config.get('osm', {}).get('buildings', {}).get('defaults', {
            'height': 10,
            'floors': 3,
            'year': 1990,
            'category': 'residential',
            'REFERENCE': ''
        })

        # Hole Buffer-Distance aus der OSM-Konfiguration
        buffer_distance = osm_config.get('osm', {}).get('buildings', {}).get('buffer_distance', 100)

        site_gdf = gpd.read_file(site_path)
        osm_buildings = fetch_surrounding_buildings(site_gdf, buffer_distance)

        if osm_buildings.empty:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return

        processed_buildings = process_osm_buildings(osm_buildings, building_defaults)
        save_surrounding_buildings(processed_buildings, geometry_path / 'surroundings.shp')

        logger.info("✅ OSM-Gebäude Abruf erfolgreich abgeschlossen!")

    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}", exc_info=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()

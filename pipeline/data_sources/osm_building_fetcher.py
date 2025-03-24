import osmnx as ox
import geopandas as gpd
from shapely.ops import unary_union
from pathlib import Path
import yaml
import logging
import sys
import os
import overpy
from shapely.geometry import Polygon, MultiPolygon
from pyproj import Transformer
from pyproj import transform
import pandas as pd
from core.config_manager import load_config

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

logger = logging.getLogger(__name__)

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

        # OSM-Abfrage mit geometries_from_polygon
        buildings_gdf = ox.geometries_from_polygon(
            search_wgs84.geometry.iloc[0],
            tags={'building': True}
        )

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

        # Verarbeite Gebäudeattribute
        processed_buildings = []
        for idx, row in buildings_gdf.iterrows():
            try:
                if not hasattr(row.geometry, 'exterior'):
                    continue

                # Hole Stockwerke mit Fehlerbehandlung
                try:
                    floors = row.get('building:levels')
                    if pd.isna(floors):
                        floors = building_defaults['floors']
                    else:
                        floors = int(float(floors))
                except (ValueError, TypeError):
                    floors = building_defaults['floors']

                # Hole Höhe mit Fehlerbehandlung
                try:
                    height = row.get('height')
                    if pd.isna(height):
                        height = building_defaults['height']
                    else:
                        height = float(height)
                except (ValueError, TypeError):
                    height = building_defaults['height']

                processed_buildings.append({
                    'Name': f'OSM_{idx}',
                    'height_ag': height,
                    'floors_ag': floors,
                    'category': 'residential',
                    'REFERENCE': '',
                    'geometry': row.geometry
                })
            except Exception as e:
                logger.warning(f"⚠️ Fehler bei der Verarbeitung eines Gebäudes: {str(e)}")
                continue

        if not processed_buildings:
            logger.warning("⚠️ Keine gültigen Gebäude gefunden!")
            return gpd.GeoDataFrame(
                columns=['Name', 'height_ag', 'floors_ag', 'category', 'REFERENCE', 'geometry'],
                geometry='geometry',
                crs=original_crs
            )

        buildings_gdf = gpd.GeoDataFrame(processed_buildings, crs=original_crs)
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

def fetch_osm_buildings(site_gdf, distance=100, config=None):
    """Lädt OSM-Gebäude im Umkreis des Standorts"""
    try:
        logger.info(f"🔍 Hole OSM-Gebäude mit {distance}m Abstand")
        buildings_gdf = fetch_surrounding_buildings(site_gdf, config)

        if buildings_gdf.empty:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)

        return buildings_gdf
    except Exception as e:
        logger.error(f"❌ Fehler beim Abruf der OSM-Gebäude: {str(e)}", exc_info=True)
        return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)

def main():
    try:
        logger.info("🚀 Starte OSM-Gebäude Abruf...")
        
        # Lade globale Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        global_config_path = root_dir / 'config' / 'global.yml'
        logger.info(f"📂 Lade globale Konfiguration: {global_config_path}")
        global_config = load_config(global_config_path)
        
        if not global_config:
            raise ValueError("❌ Keine gültige globale Konfiguration gefunden")

        # Lade OSM-spezifische Konfiguration
        osm_config_path = root_dir / 'config' / 'osm' / 'config.yml'
        logger.info(f"📂 Lade OSM-Konfiguration: {osm_config_path}")
        osm_config = load_config(osm_config_path)

        if not osm_config:
            raise ValueError("❌ Keine gültige OSM-Konfiguration gefunden")

        # Hole Pfade aus der globalen Konfiguration
        paths = global_config.get('project', {}).get('paths', {})
        if not paths:
            raise ValueError("❌ Keine Pfade in der globalen Konfiguration gefunden")

        # Setze Pfade für Geometrie und Output
        geometry_path = Path(paths.get('outputs', {}).get('buildings'))
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
        osm_buildings = fetch_osm_buildings(site_gdf, distance=buffer_distance)

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

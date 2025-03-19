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

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.config_loader import load_config

logger = logging.getLogger(__name__)

def fetch_surrounding_buildings(site_gdf: gpd.GeoDataFrame, config: dict) -> gpd.GeoDataFrame:
    """Holt Gebäude aus OpenStreetMap im Umkreis des Standorts.
    
    Args:
        site_gdf (gpd.GeoDataFrame): GeoDataFrame mit dem Site-Polygon
        config (dict): Konfiguration für die Umgebungsgebäude
        
    Returns:
        gpd.GeoDataFrame: GeoDataFrame mit den Umgebungsgebäuden
    """
    try:
        if site_gdf is None or site_gdf.empty:
            logger.error("⚠️ Ungültiges oder leeres site_gdf übergeben")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs if site_gdf is not None else "EPSG:31256")

        # Hole Konfigurationswerte
        buffer_distance = config.get('buildings', {}).get('buffer_distance', 100)
        building_defaults = config.get('buildings', {}).get('defaults', {
            'height': 10,
            'floors': 3,
            'year': 1990
        })
        
        logger.info(f"📡 OSM-Abfrage: Gebäude im Umkreis von {buffer_distance}m")

        # Konvertiere zu WGS84 für OSM-Abfrage
        site_wgs84 = site_gdf.to_crs("EPSG:4326")
        
        # Erstelle Buffer für Suche
        search_area = site_wgs84.geometry.buffer(buffer_distance).unary_union
        
        # Erstelle Overpass-Query für Gebäude
        bbox = search_area.bounds  # (minx, miny, maxx, maxy)
        overpass_query = f"""
            [out:json][timeout:180];
            (
              way["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
              relation["building"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
            );
            out body;
            >;
            out skel qt;
        """
        
        # Führe Overpass-Query aus
        api = overpy.Overpass()
        result = api.query(overpass_query)
        
        if not result.ways and not result.relations:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)

        # Verarbeite Gebäude
        buildings = []
        for way in result.ways:
            try:
                coords = [(float(node.lon), float(node.lat)) for node in way.nodes]
                if len(coords) >= 3:
                    poly = Polygon(coords)
                    buildings.append({
                        'geometry': poly,
                        'osm_id': way.id,
                        'height': way.tags.get('height', building_defaults['height']),
                        'floors': way.tags.get('building:levels', building_defaults['floors']),
                        'year': way.tags.get('start_date', building_defaults['year']),
                        'building_type': way.tags.get('building', 'yes')
                    })
            except Exception as e:
                logger.warning(f"⚠️ Fehler bei der Verarbeitung eines Gebäudes: {str(e)}")
                continue

        if not buildings:
            logger.warning("⚠️ Keine gültigen Gebäude gefunden!")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)

        # Erstelle GeoDataFrame
        buildings_gdf = gpd.GeoDataFrame(buildings, crs="EPSG:4326")
        
        # Konvertiere zum ursprünglichen CRS
        buildings_gdf = buildings_gdf.to_crs(site_gdf.crs)
        
        # Filtere Gebäude im Suchbereich
        buildings_gdf = buildings_gdf[buildings_gdf.geometry.intersects(search_area)]
        
        logger.info(f"✅ OSM-Gebäude gefunden: {len(buildings_gdf)}")
        return buildings_gdf

    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}")
        if site_gdf is not None:
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")

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

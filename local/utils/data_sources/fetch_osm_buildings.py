import osmnx as ox
import geopandas as gpd
from shapely.ops import unary_union
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)

def fetch_surrounding_buildings(site_gdf, distance=100):
    """Holt Gebäude aus OpenStreetMap im Umkreis des Standorts"""
    try:
        logger.info(f"📡 OSM-Abfrage: Gebäude im Umkreis von {distance}m")

        if site_gdf.empty:
            raise ValueError("⚠️ Fehler: Das übergebene Standortpolygon ist leer!")

        site_polygon = site_gdf.geometry.iloc[0]

        # Erstelle äußeren Buffer für Umgebungssuche
        outer_buffer = site_polygon.buffer(distance)
        buffer_gdf = gpd.GeoDataFrame(geometry=[outer_buffer], crs=site_gdf.crs)
        buffer_wgs84 = buffer_gdf.to_crs("EPSG:4326")

        logger.debug(f"🔍 OSM-Suchbereich (WGS84 Bounds): {buffer_wgs84.total_bounds}")

        # Hole Gebäude aus OSM
        tags = {'building': True}
        buildings_gdf = ox.features_from_polygon(buffer_wgs84.geometry.iloc[0], tags=tags)

        if buildings_gdf.empty:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)

        # Konvertiere zurück zum ursprünglichen CRS
        buildings_gdf = buildings_gdf.to_crs(site_gdf.crs)

        # Filtere Gebäude, die sich außerhalb des Standorts befinden
        outside_site = ~buildings_gdf.geometry.within(site_polygon)
        within_search_area = buildings_gdf.geometry.intersects(outer_buffer)
        buildings_gdf = buildings_gdf[outside_site & within_search_area]

        logger.info(f"✅ OSM-Gebäude gefunden: {len(buildings_gdf)}")
        return buildings_gdf

    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}", exc_info=True)
        return gpd.GeoDataFrame(geometry=[], crs=site_gdf.crs)


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


def load_config():
    """Lädt die Projekt-Konfiguration für OSM-Gebäude"""
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / 'cfg' / 'project_config.yml'
        logger.info(f"📂 Lade OSM-Konfiguration: {config_path}")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        return config.get('surroundings', {})

    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Projekt-Konfiguration: {str(e)}", exc_info=True)
        return None


def fetch_osm_buildings(site_gdf, distance=100, config=None):
    """Lädt OSM-Gebäude im Umkreis des Standorts"""
    try:
        logger.info(f"🔍 Hole OSM-Gebäude mit {distance}m Abstand")
        buildings_gdf = fetch_surrounding_buildings(site_gdf, distance)

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
        config = load_config()
        if not config:
            raise ValueError("❌ Keine gültige Konfiguration gefunden")

        osm_defaults = config.get('osm_defaults', {
            'default_floors': 3,
            'floor_height': 3,
            'category': 'residential',
            'REFERENCE': ''
        })

        geometry_path = Path(config['paths']['output']['geometry'])
        site_path = geometry_path / 'site.shp'

        if not site_path.exists():
            raise FileNotFoundError(f"❌ site.shp nicht gefunden in {site_path}")

        site_gdf = gpd.read_file(site_path)
        osm_buildings = fetch_osm_buildings(site_gdf, distance=config['surroundings']['surrounding_buildings_distance'])

        if osm_buildings.empty:
            logger.warning("⚠️ Keine OSM-Gebäude gefunden!")
            return

        processed_buildings = process_osm_buildings(osm_buildings, osm_defaults)
        save_surrounding_buildings(processed_buildings, geometry_path / 'surroundings.shp')

        logger.info("✅ OSM-Gebäude Abruf erfolgreich abgeschlossen!")

    except Exception as e:
        logger.error(f"❌ Fehler beim OSM-Gebäude Abruf: {str(e)}", exc_info=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()

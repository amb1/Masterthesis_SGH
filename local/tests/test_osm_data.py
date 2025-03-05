from pathlib import Path
import geopandas as gpd
import yaml
from utils.data_sources.fetch_osm_buildings import fetch_surrounding_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets

# Lade Konfigurationen
with open('local/cfg/geometry/geometry_config.yml', 'r') as f:
    geometry_config = yaml.safe_load(f)
with open('local/cfg/data_sources/osm_config.yml', 'r') as f:
    osm_config = yaml.safe_load(f)

# Lade Site Polygon
site_polygon = gpd.read_file('tests/output/site_polygon.shp')

# Test OSM Gebäude
osm_buildings = fetch_surrounding_buildings(site_polygon, geometry_config)
if osm_buildings is not None:
    osm_buildings.to_file('tests/output/osm_buildings.shp')

# Test OSM Straßen
osm_streets = fetch_osm_streets(site_polygon, {
    'osm': osm_config,
    'geometry': geometry_config
})
if osm_streets is not None:
    osm_streets.to_file('tests/output/osm_streets.shp') 
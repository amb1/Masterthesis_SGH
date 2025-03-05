from pathlib import Path
import geopandas as gpd
from utils.data_processing.create_site_polygon import create_site_polygon
import yaml

# Lade Konfiguration
with open('local/cfg/geometry/geometry_config.yml', 'r') as f:
    geometry_config = yaml.safe_load(f)

# Lade gespeicherte Gebäude aus vorherigem Test
buildings_gdf = gpd.read_file('tests/output/buildings.shp')

# Erstelle Site Polygon
site_polygon = create_site_polygon(buildings_gdf, geometry_config)

# Speichere für visuelle Inspektion
site_polygon.to_file('tests/output/site_polygon.shp') 
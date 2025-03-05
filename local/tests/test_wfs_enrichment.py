from pathlib import Path
import geopandas as gpd
import yaml
from utils.data_sources.fetch_wfs_data import ViennaWFS

# Lade Konfigurationen
with open('local/cfg/wfs/wfs_config.yml', 'r') as f:
    wfs_config = yaml.safe_load(f)

# Lade gespeicherte Daten
buildings_gdf = gpd.read_file('tests/output/buildings.shp')
site_polygon = gpd.read_file('tests/output/site_polygon.shp')

# Test WFS Anreicherung
wfs = ViennaWFS(wfs_config)
enriched_buildings = wfs.enrich_buildings(buildings_gdf, site_polygon)

# Speichere Ergebnis
if enriched_buildings is not None:
    enriched_buildings.to_file('tests/output/enriched_buildings.shp') 
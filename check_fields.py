import geopandas as gpd
import pandas as pd

# Überprüfe zone.shp
zone_gdf = gpd.read_file('local/projects/test2/test/inputs/building-geometry/zone.shp')
print('\nZone.shp Felder:')
print(zone_gdf.columns.tolist())

# Überprüfe typology.shp
typology_gdf = gpd.read_file('local/projects/test2/test/inputs/building-properties/typology.shp')
print('\nTypology.shp Felder:')
print(typology_gdf.columns.tolist()) 
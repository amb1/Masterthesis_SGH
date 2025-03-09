import geopandas as gpd
import pandas as pd

# Lade die Daten
citygml = gpd.read_file('local/data/outputs/citygml/buildings_raw.shp')
fmzk = gpd.read_file('local/data/outputs/citygml/fmzk.shp')

# Berechne Flächen
citygml['area'] = citygml.geometry.area
fmzk['area'] = fmzk.geometry.area

# Statistik für CityGML
print("CityGML Flächenstatistik:")
print(f"Minimum: {citygml.area.min():.1f}m²")
print(f"Maximum: {citygml.area.max():.1f}m²")
print(f"Mittelwert: {citygml.area.mean():.1f}m²")
print(f"Median: {citygml.area.median():.1f}m²")
print(f"Gesamtfläche: {citygml.area.sum():.1f}m²")
print("\nVerteilung CityGML:")
print(f"< 100m²: {len(citygml[citygml.area < 100])}")
print(f"100-500m²: {len(citygml[(citygml.area >= 100) & (citygml.area < 500)])}")
print(f"500-1000m²: {len(citygml[(citygml.area >= 500) & (citygml.area < 1000)])}")
print(f"> 1000m²: {len(citygml[citygml.area >= 1000])}")

print("\nFMZK Flächenstatistik:")
print(f"Minimum: {fmzk.area.min():.1f}m²")
print(f"Maximum: {fmzk.area.max():.1f}m²")
print(f"Mittelwert: {fmzk.area.mean():.1f}m²")
print(f"Median: {fmzk.area.median():.1f}m²")
print(f"Gesamtfläche: {fmzk.area.sum():.1f}m²")
print("\nVerteilung FMZK:")
print(f"< 100m²: {len(fmzk[fmzk.area < 100])}")
print(f"100-500m²: {len(fmzk[(fmzk.area >= 100) & (fmzk.area < 500)])}")
print(f"500-1000m²: {len(fmzk[(fmzk.area >= 500) & (fmzk.area < 1000)])}")
print(f"> 1000m²: {len(fmzk[fmzk.area >= 1000])}") 
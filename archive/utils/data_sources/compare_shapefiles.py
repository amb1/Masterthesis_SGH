"""
import geopandas as gpd
import logging
from pathlib import Path
import os
import sys

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

def compare_shapefiles():
    try:
        # Absolute Pfade
        base_path = Path("E:/ambi/Code/SGH-Master-Github")
        citygml_path = base_path / "local/data/outputs/citygml/buildings_raw.shp"
        fmzk_path = base_path / "local/data/outputs/citygml/fmzk.shp"
        
        print(f"Suche nach Dateien:", flush=True)
        print(f"CityGML Pfad: {citygml_path}", flush=True)
        print(f"FMZK Pfad: {fmzk_path}", flush=True)
        
        if not citygml_path.exists():
            print(f"CityGML Shapefile nicht gefunden: {citygml_path}", flush=True)
            return
            
        if not fmzk_path.exists():
            print(f"FMZK Shapefile nicht gefunden: {fmzk_path}", flush=True)
            return
        
        # Lade die Daten
        print("\nLade Shapefiles...", flush=True)
        citygml_gdf = gpd.read_file(citygml_path)
        fmzk_gdf = gpd.read_file(fmzk_path)
        
        # Vergleiche CRS
        print("\nKoordinatensysteme:", flush=True)
        print(f"CityGML CRS: {citygml_gdf.crs}", flush=True)
        print(f"FMZK CRS: {fmzk_gdf.crs}", flush=True)
        
        # Vergleiche Bounds
        print("\nBounding Boxes:", flush=True)
        print(f"CityGML Bounds: {citygml_gdf.total_bounds}", flush=True)
        print(f"FMZK Bounds: {fmzk_gdf.total_bounds}", flush=True)
        
        # Vergleiche Geometrietypen
        print("\nGeometrietypen:", flush=True)
        print(f"CityGML Geometrietypen: {citygml_gdf.geom_type.unique()}", flush=True)
        print(f"FMZK Geometrietypen: {fmzk_gdf.geom_type.unique()}", flush=True)
        
        # Vergleiche Spalten
        print("\nSpalten:", flush=True)
        print(f"CityGML Spalten: {citygml_gdf.columns.tolist()}", flush=True)
        print(f"FMZK Spalten: {fmzk_gdf.columns.tolist()}", flush=True)
        
        # Berechne einige Statistiken
        print("\nStatistiken:", flush=True)
        print(f"Anzahl CityGML Gebäude: {len(citygml_gdf)}", flush=True)
        print(f"Anzahl FMZK Gebäude: {len(fmzk_gdf)}", flush=True)
        
        # Berechne durchschnittliche Fläche
        citygml_area = citygml_gdf.geometry.area.mean()
        fmzk_area = fmzk_gdf.geometry.area.mean()
        print(f"Durchschnittliche Fläche CityGML: {citygml_area:.2f}", flush=True)
        print(f"Durchschnittliche Fläche FMZK: {fmzk_area:.2f}", flush=True)
        
        # Prüfe auf ungültige Geometrien
        print("\nUngültige Geometrien:", flush=True)
        print(f"CityGML ungültige Geometrien: {(~citygml_gdf.geometry.is_valid).sum()}", flush=True)
        print(f"FMZK ungültige Geometrien: {(~fmzk_gdf.geometry.is_valid).sum()}", flush=True)

        # Vergleiche die Koordinatenbereiche detaillierter
        print("\nKoordinatenbereiche im Detail:", flush=True)
        for gdf, name in [(citygml_gdf, "CityGML"), (fmzk_gdf, "FMZK")]:
            x_min, y_min = gdf.geometry.bounds[["minx", "miny"]].min()
            x_max, y_max = gdf.geometry.bounds[["maxx", "maxy"]].max()
            print(f"\n{name} Koordinaten:", flush=True)
            print(f"X-Bereich: {x_min:.2f} bis {x_max:.2f}", flush=True)
            print(f"Y-Bereich: {y_min:.2f} bis {y_max:.2f}", flush=True)

    except Exception as e:
        print(f"Fehler beim Vergleich: {str(e)}", flush=True)
        import traceback
        print(traceback.format_exc(), flush=True)

if __name__ == "__main__":
    compare_shapefiles()
""" 
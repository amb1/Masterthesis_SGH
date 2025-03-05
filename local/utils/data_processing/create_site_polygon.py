import geopandas as gpd
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
import numpy as np
from pathlib import Path
import yaml
import sys

def create_site_polygon(buildings_gdf: gpd.GeoDataFrame, buffer_distance: float = 3) -> gpd.GeoDataFrame:
    """Erstellt ein einzelnes Polygon, das alle Gebäude umschließt"""
    if 'geometry' not in buildings_gdf.columns or buildings_gdf.geometry.isnull().all():
        print("⚠️ Warnung: buildings_gdf enthält keine gültigen Geometrien")
        site_polygon = box(*buildings_gdf.total_bounds)
    else:
        print("📐 Erstelle äußere Hülle um alle Gebäude")
        all_buildings = unary_union(buildings_gdf.geometry)
        
        print(f"🔲 Erstelle Buffer mit Abstand {buffer_distance}m")
        site_polygon = all_buildings.convex_hull.buffer(buffer_distance)
        site_polygon = site_polygon.simplify(tolerance=0.5)

    site_gdf = gpd.GeoDataFrame(
        {'Name': ['Site'],
         'geometry': [site_polygon]},
        crs=buildings_gdf.crs
    )

    print("✅ Standortpolygon erstellt:")
    print(f"- Fläche: {site_polygon.area:.2f} m²")
    print(f"- Umfang: {site_polygon.length:.2f} m")

    return site_gdf

def save_site_polygon(site_gdf, output_path):
    """Speichert das Site-Polygon als Shapefile"""
    print(f"Speichere Site-Polygon nach: {output_path}")
    site_gdf.to_file(output_path, driver='ESRI Shapefile')
    print("Site-Polygon erfolgreich gespeichert")

def load_config():
    """Lädt die Konfiguration"""
    try:
        # Absoluter Pfad zur Konfigurationsdatei
        config_path = Path(__file__).resolve().parent.parent.parent / 'cfg' / 'project_config.yml'
        print(f"Lade Konfiguration: {config_path}")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        return config.get('surroundings', {})
        
    except Exception as e:
        print(f"Fehler beim Laden der Konfiguration: {str(e)}")
        return None

def main():
    try:
        print("Starte Site-Polygon Erstellung...")
        
        # Lade Konfiguration
        config = load_config()
        print("Konfiguration geladen")
        
        # Erstelle Pfade
        geometry_path = Path(config['paths']['output']['geometry'])
        zone_path = geometry_path / 'zone.shp'
        
        # Überprüfe ob zone.shp existiert
        if not zone_path.exists():
            raise FileNotFoundError(f"zone.shp nicht gefunden in {zone_path}")
        
        # Erstelle Site-Polygon
        site_gdf = create_site_polygon(
            zone_path,
            config
        )
        
        # Speichere Site-Polygon
        save_site_polygon(site_gdf, geometry_path / 'site.shp')
        
        print("Site-Polygon Erstellung erfolgreich abgeschlossen!")
        
    except Exception as e:
        print(f"Fehler bei der Site-Polygon Erstellung: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
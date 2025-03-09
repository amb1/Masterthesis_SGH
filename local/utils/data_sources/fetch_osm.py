import geopandas as gpd
import logging
from typing import Optional
from pathlib import Path
import yaml
import time
import osmnx as ox

# Logger einrichten
logger = logging.getLogger("OSMFetcher")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class OSMFetcher:
    """Klasse für den Zugriff auf OpenStreetMap-Daten."""
    
    def __init__(self, config: dict):
        """Initialisiert den OSM-Fetcher.
        
        Args:
            config (dict): Konfiguration für OSM
        """
        if not isinstance(config, dict):
            raise ValueError("config muss ein Dictionary sein")
            
        self.config = config.get('osm', {})
        self.timeout = self.config.get('timeout', 30)
        self.retries = self.config.get('retries', 3)
        self.tags = self.config.get('tags', {})
        
        logger.info("✅ OSM-Fetcher initialisiert")

    def fetch_data(self, site_polygon: gpd.GeoDataFrame) -> Optional[gpd.GeoDataFrame]:
        """Lädt OSM-Daten für den gegebenen Bereich.
        
        Args:
            site_polygon (gpd.GeoDataFrame): GeoDataFrame mit dem Untersuchungsgebiet
            
        Returns:
            Optional[gpd.GeoDataFrame]: Geladene Daten oder None bei Fehler
        """
        try:
            logger.info("🔄 Lade OSM-Daten...")
            
            # Konvertiere das Untersuchungsgebiet in WGS84 für OSM
            site_polygon_wgs84 = site_polygon.to_crs("EPSG:4326")
            
            # Hole Gebäude
            buildings = ox.features_from_polygon(
                site_polygon_wgs84.geometry[0],
                tags={'building': True}
            )
            
            if buildings is not None and not buildings.empty:
                # Konvertiere zurück in das Projekt-CRS
                buildings = buildings.to_crs(site_polygon.crs)
                logger.info(f"✅ {len(buildings)} Gebäude geladen")
                return buildings
            else:
                logger.warning("⚠️ Keine Gebäude gefunden")
                return None
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der OSM-Daten: {str(e)}", exc_info=True)
            return None

if __name__ == "__main__":
    print("🔎 OSM Daten Test-Modus")
    try:
        # Lade Projekt-Konfiguration
        config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "project_config.yml"
        with open(config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)

        from shapely.geometry import box
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")

        fetcher = OSMFetcher(config)
        data = fetcher.fetch_data(test_gdf)
        
        if data is not None:
            print(f"✅ Test erfolgreich: {len(data)} Features geladen")
        else:
            print("❌ Test fehlgeschlagen")

    except Exception as e:
        logger.error(f"❌ Fehler im Test-Modus: {str(e)}", exc_info=True) 
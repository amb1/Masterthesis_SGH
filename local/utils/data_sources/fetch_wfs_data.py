from owslib.wfs import WebFeatureService
import geopandas as gpd
import yaml
from typing import Optional
from pathlib import Path
import logging

# Logger einrichten
logger = logging.getLogger("ViennaWFS")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class ViennaWFS:
    """Klasse für den Zugriff auf den Wiener WFS-Service."""
    
    def __init__(self, config: dict):
        """Initialisiert den WFS-Service.
        
        Args:
            config (dict): WFS-Konfiguration
        """
        if not isinstance(config, dict):
            raise ValueError("config muss ein Dictionary sein")
            
        if 'vienna_wfs' not in config:
            raise ValueError("config muss einen 'vienna_wfs' Schlüssel haben")
            
        self.config = config['vienna_wfs']
        self.url = self.config.get('url', 'https://data.wien.gv.at/daten/geo')
        self.version = self.config.get('version', '2.0.0')
        self.timeout = self.config.get('timeout', 30)
        self.retries = self.config.get('retries', 3)
        self.crs = "urn:x-ogc:def:crs:EPSG:31256"  # Korrigiertes CRS-Format
        self.merge_fields = self.config.get('merge_fields', {})
        self.layers = self.config.get('layers', {})
        self.field_mapping = self.config.get('field_mapping', {})
        self.streams = self.config.get('streams', [])
        
        # Initialisiere WFS-Client
        self.wfs = WebFeatureService(
            self.url,
            version=self.version,
            timeout=self.timeout
        )
        
        logger.info(f"✅ WFS-Service initialisiert: {self.url}")

    def fetch_building_model(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt das Baukörpermodell"""
        try:
            logger.info("Lade Baukörpermodell...")
            # Prüfe ob bbox gültige Werte enthält
            if bbox is None or any(map(lambda x: x != x, bbox)):  # Prüft auf NaN
                logger.error("❌ Ungültige Bounding Box für WFS-Abfrage")
                return None
            
            response = self.wfs.getfeature(
                typename='ogdwien:FMZKBKMOGD',
                bbox=bbox,
                srsname=self.crs
            )
            
            buildings_gdf = gpd.read_file(response)

            if 'geometry' not in buildings_gdf.columns:
                logger.error("❌ WFS-Daten enthalten keine Geometrie! Überprüfe die Abfrage.")
                return None

            buildings_gdf["height"] = buildings_gdf["O_KOTE"].astype(float) - buildings_gdf["U_KOTE"].astype(float)

            logger.info(f"✅ {len(buildings_gdf)} Gebäude geladen")
            return buildings_gdf

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden des Baukörpermodells: {str(e)}", exc_info=True)
            return None

    def fetch_building_typology(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt die Gebäudetypologie für den gegebenen Bereich"""
        try:
            logger.info("Lade Gebäudetypologie...")
            response = self.wfs.getfeature(
                typename='ogdwien:GEBAEUDETYPOGD',
                bbox=bbox,
                srsname=self.crs
            )
            typology_gdf = gpd.read_file(response)

            if 'geometry' not in typology_gdf.columns:
                logger.error("❌ Fehler: WFS-Daten enthalten keine Geometrie!")
                return None

            return typology_gdf

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Gebäudetypologie: {str(e)}", exc_info=True)
            return None

    def enrich_with_wfs(self, buildings_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Reichert die Gebäude mit WFS-Daten an.
        
        Args:
            buildings_gdf (gpd.GeoDataFrame): GeoDataFrame mit den Gebäuden
            
        Returns:
            gpd.GeoDataFrame: Angereichertes GeoDataFrame
        """
        try:
            # Hole WFS-Daten für alle konfigurierten Streams
            for stream in self.streams:
                layer_name = stream['layer']
                mapping = stream.get('mapping', {})
                
                # Hole die WFS-Daten
                wfs_data = self.fetch_layer(layer_name, buildings_gdf.total_bounds)
                if not wfs_data.empty:
                    # Konvertiere zu GeoDataFrame falls nötig
                    if not isinstance(wfs_data, gpd.GeoDataFrame):
                        wfs_data = gpd.GeoDataFrame(wfs_data, crs=self.crs)
                    
                    # Führe die Daten zusammen
                    buildings_gdf = buildings_gdf.merge(
                        wfs_data,
                        on='building_id',
                        how='left'
                    )
            
            return buildings_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der WFS-Anreicherung: {str(e)}")
            return buildings_gdf

    def fetch_layer(self, layer_name, bbox=None) -> Optional[gpd.GeoDataFrame]:
        """Lädt einen WFS Layer und validiert Geometrie"""
        try:
            logger.info(f"Lade WFS Layer: {layer_name}")
            typename = layer_name if "ogdwien:" in layer_name else f"ogdwien:{layer_name}"
            
            # Konvertiere bbox in das richtige Format
            if bbox is not None:
                bbox = [float(x) for x in bbox]
            
            response = self.wfs.getfeature(
                typename=typename,
                bbox=bbox,
                srsname=self.crs
            )
            
            data_gdf = gpd.read_file(response)

            if data_gdf is None or data_gdf.empty:
                logger.warning(f"⚠️ Keine Daten für Layer {layer_name} erhalten")
                return None

            if 'geometry' not in data_gdf.columns:
                raise ValueError(f"❌ Fehler: 'geometry'-Spalte fehlt im WFS-DataFrame für {layer_name}")

            return gpd.GeoDataFrame(data_gdf, geometry='geometry', crs="EPSG:31256")

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden des Layers {layer_name}: {str(e)}", exc_info=True)
            return None


def fetch_wfs_data(site_polygon, layer_name, config):
    """Holt WFS-Daten für einen bestimmten Layer"""
    try:
        # Hole WFS-Streams aus der wfs_config.yml
        wfs_config = config.get('wfs', {})
        streams = wfs_config.get('streams', [])
        stream_config = next((s for s in streams if s['layer'] == layer_name), None)
        
        if not stream_config:
            logger.warning(f"⚠️ Keine Stream-Konfiguration gefunden für Layer: {layer_name}")
            return None
            
        # Hole die WFS-Daten
        wfs = ViennaWFS(wfs_config)
        return wfs.fetch_layer(layer_name, site_polygon.total_bounds)
        
    except Exception as e:
        logger.error(f"❌ Fehler beim WFS-Datenabruf: {str(e)}")
        return None


if __name__ == "__main__":
    print("🔎 WFS Daten Test-Modus")
    try:
        # Lade Projekt-Konfiguration
        config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "project_config.yml"
        with open(config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Lade WFS-Konfiguration
        wfs_config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "wfs" / "wfs_config.yml"
        with open(wfs_config_path, 'r', encoding="utf-8") as f:
            wfs_config = yaml.safe_load(f)

        # Kombiniere Konfigurationen
        config['vienna_wfs'] = wfs_config['vienna_wfs']

        from shapely.geometry import box
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")

        for stream in config.get('data_sources', {}).get('wfs_streams', []):
            try:
                data = fetch_wfs_data(test_gdf, stream['layer'], config)
                if data is not None:
                    print(f"✅ Stream-Test erfolgreich: {stream['name']}")
            except Exception as e:
                print(f"❌ Fehler bei Stream {stream['name']}: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Fehler im Test-Modus: {str(e)}", exc_info=True)

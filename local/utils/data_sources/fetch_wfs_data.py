from owslib.wfs import WebFeatureService
import geopandas as gpd
import yaml
from typing import Optional
from pathlib import Path
import logging
import io
import pandas as pd
from pyproj import Transformer
import requests

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
            
        # Extrahiere die vienna_wfs Konfiguration
        if 'vienna_wfs' in config:
            self.config = config['vienna_wfs']
        else:
            self.config = config  # Nimm an, dass die Konfiguration bereits die vienna_wfs Daten enthält
            
        self.url = self.config.get('url', 'https://data.wien.gv.at/daten/geo')
        self.version = self.config.get('version', '1.1.0')
        self.timeout = self.config.get('timeout', 30)
        self.retries = self.config.get('retries', 3)
        self.crs = "urn:x-ogc:def:crs:EPSG:31256"  # Korrektes URN-Format für Wien
        self.merge_fields = self.config.get('merge_fields', {})
        self.layers = self.config.get('layers', {})
        self.field_mapping = self.config.get('field_mapping', {})
        self.streams = self.config.get('streams', [])
        
        # Initialisiere WFS-Client nur einmal
        if not hasattr(self, '_wfs'):
            self._wfs = WebFeatureService(
                url=self.url,
                version=self.version,
                timeout=self.timeout
            )
            logger.info(f"✅ WFS-Service initialisiert: {self.url}")

    @property
    def wfs(self):
        return self._wfs

    def fetch_layer(self, layer_name: str, bbox=None) -> Optional[gpd.GeoDataFrame]:
        """Lädt einen WFS Layer und validiert Geometrie
        
        Args:
            layer_name (str): Name des WFS Layers
            bbox (list, optional): Bounding Box [minlon, minlat, maxlon, maxlat] in EPSG:4326
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit den Layer-Daten oder None bei Fehler
        """
        try:
            logger.info(f"🔄 Lade WFS Layer: {layer_name}")
            
            # Konstruiere die URL direkt
            url = f"{self.url}?service=WFS&version={self.version}&request=GetFeature&typeName={layer_name}&maxFeatures=50"
            
            if bbox is not None:
                # Validiere bbox
                if any(pd.isna(coord) for coord in bbox):
                    logger.warning("⚠️ Ungültige Bounding Box mit NaN Werten")
                    return None
                    
                # Füge BBOX als separaten Parameter hinzu
                bbox_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]},EPSG:4326"
                url += f"&BBOX={bbox_str}"
                logger.info(f"📍 BBOX: {bbox_str}")
            
            # Hole WFS-Daten direkt über die URL
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"❌ Fehler beim Abruf der WFS-Daten: {response.status_code}")
                logger.error(f"URL: {url}")
                return None
            
            # Parse GeoJSON
            try:
                # Konvertiere zu GeoDataFrame
                gdf = gpd.read_file(io.BytesIO(response.content))
                
                # Prüfe auf Geometrie-Spalte
                if 'geometry' not in gdf.columns:
                    logger.warning(f"⚠️ Keine Geometrie-Spalte in Layer {layer_name}")
                    return None
                    
                # Konvertiere OBJECTID zu String
                if 'OBJECTID' in gdf.columns:
                    gdf['OBJECTID'] = gdf['OBJECTID'].astype(str)
                    
                # Setze CRS explizit
                if gdf.crs is None:
                    gdf.set_crs("EPSG:4326", inplace=True)
                
                # Transformiere zu Wien GK East wenn nötig
                if gdf.crs != self.crs:
                    gdf = gdf.to_crs(self.crs)
                
                # Log Ergebnis
                logger.info(f"✅ {len(gdf)} Features geladen")
                logger.info(f"📊 Verfügbare Spalten: {list(gdf.columns)}")
                
                return gdf
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Parsen der GeoJSON-Daten: {str(e)}")
                return None
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden von Layer {layer_name}: {str(e)}")
            return None

    def fetch_building_model(self, bbox=None) -> Optional[gpd.GeoDataFrame]:
        """Lädt das Baukörpermodell aus dem WFS.
        
        Args:
            bbox (list, optional): Bounding Box [minx, miny, maxx, maxy]
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit Gebäudedaten oder None bei Fehler
        """
        logger.info("🔄 Lade Baukörpermodell...")
        return self.fetch_layer("ogdwien:GEBAEUDEINFOOGD", bbox)

    def fetch_building_typology(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt die Gebäudetypologie für den gegebenen Bereich"""
        try:
            logger.info("🔄 Lade Gebäudetypologie...")
            return self.fetch_layer('ogdwien:GEBAEUDETYPOGD', bbox)
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

    def fetch_data(self, bbox=None) -> dict:
        """Holt Daten von allen konfigurierten WFS-Streams.
        
        Args:
            bbox (list, optional): Bounding Box [minx, miny, maxx, maxy]
            
        Returns:
            dict: Dictionary mit Layer-Namen als Schlüssel und GeoDataFrames als Werte
        """
        try:
            logger.info("🔄 Hole Daten von allen WFS-Streams...")
            results = {}
            
            # Hole alle konfigurierten Streams aus der Konfiguration
            streams = self.config.get('streams', [])
            
            for stream in streams:
                try:
                    layer_name = stream.get('layer')
                    if not layer_name:
                        continue
                        
                    logger.info(f"📡 Verarbeite WFS-Stream: {layer_name}")
                    
                    # Hole WFS-Daten für diesen Layer
                    layer_data = self.fetch_layer(layer_name, bbox)
                    
                    if layer_data is not None and not layer_data.empty:
                        # Füge Mapping hinzu, falls vorhanden
                        mapping = stream.get('mapping', {})
                        if mapping:
                            for new_col, old_col in mapping.items():
                                if old_col in layer_data.columns:
                                    layer_data[new_col] = layer_data[old_col]
                        
                        results[layer_name] = layer_data
                        logger.info(f"✅ Layer {layer_name} erfolgreich geladen: {len(layer_data)} Features")
                    else:
                        logger.warning(f"⚠️ Keine Daten für Layer {layer_name}")
                        
                except Exception as e:
                    logger.error(f"❌ Fehler beim Verarbeiten von Stream {layer_name}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abruf der WFS-Daten: {str(e)}")
            return {}

    def fetch_all_layers(self) -> dict:
        """Holt Daten von allen verfügbaren WFS-Layern.
        
        Returns:
            dict: Dictionary mit Layer-Namen als Schlüssel und GeoDataFrames als Werte
        """
        try:
            logger.info("🔄 Hole Daten von allen verfügbaren WFS-Layern...")
            results = {}
            
            # Hole alle verfügbaren Layer vom WFS-Service
            capabilities = self.wfs.getcapabilities()
            available_layers = list(capabilities.contents)
            
            logger.info(f"📋 Verfügbare Layer: {len(available_layers)}")
            
            for layer_name in available_layers:
                try:
                    logger.info(f"📡 Verarbeite Layer: {layer_name}")
                    
                    # Hole WFS-Daten für diesen Layer
                    layer_data = self.fetch_layer(layer_name)
                    
                    if layer_data is not None and not layer_data.empty:
                        results[layer_name] = layer_data
                        logger.info(f"✅ Layer {layer_name} erfolgreich geladen: {len(layer_data)} Features")
                    else:
                        logger.warning(f"⚠️ Keine Daten für Layer {layer_name}")
                        
                except Exception as e:
                    logger.error(f"❌ Fehler beim Verarbeiten von Layer {layer_name}: {str(e)}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abruf der WFS-Layer: {str(e)}")
            return {}


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

        # Erstelle WFS Client
        wfs = ViennaWFS(config)
        
        # Hole alle verfügbaren Layer
        print("\n📋 Verfügbare WFS-Layer:")
        response = wfs.wfs.getfeature(
            typename='ogdwien:FMZKBKMOGD',
            maxfeatures=1
        )
        print(response.getvalue().decode('utf-8'))
            
        # Teste konfigurierte Streams
        print("\n🔄 Teste konfigurierte WFS-Streams:")
        
        # Teste spezifische Layer
        test_layers = [
            'ogdwien:FMZKBKMOGD',
            'ogdwien:GEBAEUDEINFOOGD',
            'ogdwien:GEBAEUDETYPOGD',
            'ogdwien:REALNUT2022OGD'
        ]
        
        # Bereich um den Stephansdom
        bbox = [16.372, 48.208, 16.374, 48.209]
        
        results = {}
        for layer in test_layers:
            try:
                print(f"\nTeste Layer: {layer}")
                data = wfs.fetch_layer(layer, bbox)
                if data is not None and not data.empty:
                    results[layer] = data
                    print(f"✅ Layer {layer} erfolgreich geladen: {len(data)} Features")
                    print("Spalten:", list(data.columns))
                else:
                    print(f"⚠️ Keine Daten für Layer {layer}")
            except Exception as e:
                print(f"❌ Fehler bei Layer {layer}: {str(e)}")
            
        # Speichere Ergebnisse
        if results:
            output_dir = Path(__file__).resolve().parent.parent.parent / "data" / "wfs"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            for layer_name, data in results.items():
                output_file = output_dir / f"{layer_name.replace(':', '_')}.geojson"
                data.to_file(output_file, driver='GeoJSON')
                print(f"\n💾 Layer {layer_name} gespeichert nach: {output_file}")

    except Exception as e:
        print(f"❌ Fehler im Test-Modus: {str(e)}")
        raise

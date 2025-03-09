from owslib.wfs import WebFeatureService
import geopandas as gpd
import yaml
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging
import io
import pandas as pd
from pyproj import Transformer
import requests
from lxml import etree
from shapely.geometry import box

# Logger einrichten
logger = logging.getLogger("ViennaWFS")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# XML Entity Resolver
class XMLResolver(etree.Resolver):
    def __init__(self):
        self.entities = {
            'uuml': 'ü',
            'auml': 'ä',
            'ouml': 'ö',
            'szlig': 'ß',
            'Auml': 'Ä',
            'Ouml': 'Ö',
            'Uuml': 'Ü'
        }

    def resolve(self, system_url, public_id, context):
        if system_url in self.entities:
            return self.resolve_string(self.entities[system_url], context)
        return None

class ViennaWFS:
    """Klasse für den Zugriff auf den Wiener WFS-Service."""
    
    def __init__(self, config_path: str = "local/cfg/wfs/wfs_config.yml"):
        """Initialisiert den WFS-Client mit der angegebenen Konfiguration."""
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        wfs_config = config.get('vienna_wfs', {})
        self.url = wfs_config.get('url')
        self.version = wfs_config.get('version', '1.1.0')
        self.timeout = wfs_config.get('timeout', 30)
        self.streams = wfs_config.get('streams', [])
        self.layers = wfs_config.get('layers', {})
        
        if not self.url:
            raise ValueError("❌ WFS URL nicht in der Konfiguration gefunden")
            
        try:
            self.wfs = WebFeatureService(url=self.url, version=self.version, timeout=self.timeout)
            logging.info("✅ WFS-Verbindung erfolgreich hergestellt")
        except Exception as e:
            logging.error(f"❌ Fehler bei WFS-Verbindung: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """Testet die WFS-Verbindung."""
        try:
            self.wfs.getcapabilities()
            logging.info("✅ WFS-Verbindung erfolgreich getestet")
            return True
        except Exception as e:
            logging.error(f"❌ WFS-Verbindungstest fehlgeschlagen: {str(e)}")
            return False

    def set_streams(self, streams: List[Dict[str, Any]]):
        """Setzt die WFS-Streams für spätere Verarbeitung.
        
        Args:
            streams (List[Dict]): Liste der Stream-Konfigurationen
        """
        self.streams = streams

    def fetch_layer(self, layer_name: str, bbox: Optional[tuple] = None, filters: Optional[Dict] = None) -> Optional[gpd.GeoDataFrame]:
        """Holt einen Layer vom WFS mit optionaler räumlicher und attributiver Filterung.
        
        Args:
            layer_name (str): Name des Layers
            bbox (tuple): Bounding Box (minx, miny, maxx, maxy)
            filters (dict): Attributfilter
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit den Layerdaten
        """
        try:
            # Baue Filter
            filter_params = {}
            if bbox:
                bbox_str = ','.join(map(str, bbox))
                filter_params['bbox'] = bbox_str
            
            if filters:
                for key, value in filters.items():
                    filter_params[key] = value

            # Hole Features
            response = self.wfs.getfeature(
                typename=layer_name,
                bbox=bbox_str if bbox else None,
                filter=filters
            )
            content = response.read()
            
            # Parse XML
            xml_tree = etree.fromstring(content, parser=self.xml_parser)
            
            # Konvertiere zu GeoDataFrame
            gdf = gpd.read_file(io.BytesIO(content))
            
            if 'geometry' not in gdf.columns:
                logger.error(f"Keine Geometrie-Spalte in Layer {layer_name} gefunden")
                return None
            
            # Konvertiere OBJECTID zu String wenn vorhanden
            if 'OBJECTID' in gdf.columns:
                gdf['OBJECTID'] = gdf['OBJECTID'].astype(str)
            
            # Setze CRS
            gdf.set_crs(self.crs, inplace=True)
            
            logger.info(f"✅ Layer {layer_name} erfolgreich geladen: {len(gdf)} Features")
            return gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen des Layers {layer_name}: {str(e)}")
            return None

    def fetch_building_model(self, config: Dict[str, Any], bbox: Optional[tuple] = None) -> Optional[gpd.GeoDataFrame]:
        """Holt das Gebäudemodell mit optionaler räumlicher Filterung.
        
        Args:
            config (Dict): Layer-Konfiguration
            bbox (tuple): Optionale Bounding Box
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit Gebäudedaten
        """
        try:
            layer_pattern = config.get('layer_pattern', '')
            available_layers = list(self.wfs.contents.keys())
            matching_layers = [layer for layer in available_layers if layer_pattern in layer]
            
            if not matching_layers:
                logger.error(f"❌ Keine Layer gefunden, die dem Muster {layer_pattern} entsprechen")
                return None
            
            building_data = []
            for layer in matching_layers:
                gdf = self.fetch_layer(layer, bbox=bbox)
                if gdf is not None:
                    building_data.append(gdf)
            
            if not building_data:
                logger.error("❌ Keine Gebäudedaten gefunden")
                return None
            
            combined_gdf = pd.concat(building_data, ignore_index=True)
            return combined_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen des Gebäudemodells: {str(e)}")
            return None

    def fetch_data(self, config: Dict[str, Any], bbox: Optional[tuple] = None) -> Dict[str, gpd.GeoDataFrame]:
        """Holt Daten für alle konfigurierten Streams.
        
        Args:
            config (Dict): Stream-Konfiguration
            bbox (tuple): Optionale Bounding Box
            
        Returns:
            Dict[str, gpd.GeoDataFrame]: Dictionary mit Layer-Namen und GeoDataFrames
        """
        try:
            results = {}
            streams = config.get('streams', self.streams)
            
            for stream in streams:
                layer_name = stream.get('layer')
                if not layer_name:
                    continue
                    
                filters = stream.get('filters', {})
                gdf = self.fetch_layer(layer_name, bbox=bbox, filters=filters)
                
                if gdf is not None:
                    results[layer_name] = gdf
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Daten: {str(e)}")
            return {}

    def fetch_building_typology(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt die Gebäudetypologie für den gegebenen Bereich"""
        try:
            logger.info("🔄 Lade Gebäudetypologie...")
            return self.fetch_layer('ogdwien:GEBAEUDETYPOGD', bbox)
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Gebäudetypologie: {str(e)}", exc_info=True)
            return None

    def enrich_with_wfs(self, buildings_gdf: gpd.GeoDataFrame, bbox: Optional[tuple] = None) -> gpd.GeoDataFrame:
        """Reichert Gebäudedaten mit WFS-Daten an.
        
        Args:
            buildings_gdf (gpd.GeoDataFrame): Ursprüngliche Gebäudedaten
            bbox (tuple): Optionale Bounding Box
            
        Returns:
            gpd.GeoDataFrame: Angereicherte Gebäudedaten
        """
        try:
            enriched_gdf = buildings_gdf.copy()
            
            for stream in self.streams:
                layer_name = stream.get('layer')
                mapping = stream.get('mapping', {})
                join_type = stream.get('join_type', 'nearest')
                
                # Hole WFS-Daten
                wfs_data = self.fetch_layer(layer_name, bbox=bbox)
                if wfs_data is None or wfs_data.empty:
                    continue
                
                # Führe räumliche Verknüpfung durch
                if join_type == 'nearest':
                    joined = gpd.sjoin_nearest(
                        enriched_gdf,
                        wfs_data,
                        how='left',
                        distance_col='distance'
                    )
                else:
                    joined = gpd.sjoin(
                        enriched_gdf,
                        wfs_data,
                        how='left',
                        predicate='intersects'
                    )
                
                # Wende Mapping an
                for target_col, source_col in mapping.items():
                    if source_col in joined.columns:
                        enriched_gdf[target_col] = joined[source_col]
            
            return enriched_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der WFS-Anreicherung: {str(e)}")
            return buildings_gdf

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
        return wfs.fetch_layer(layer_name)
        
    except Exception as e:
        logger.error(f"❌ Fehler beim WFS-Datenabruf: {str(e)}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("🔎 WFS Daten Test-Modus")
    
    try:
        wfs = ViennaWFS()
        if wfs.test_connection():
            logging.info("✅ WFS-Test erfolgreich abgeschlossen")
        else:
            logging.error("❌ WFS-Test fehlgeschlagen")
    except Exception as e:
        logging.error(f"❌ Fehler im Test-Modus: {str(e)}")

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
from shapely.geometry import box, Polygon
import sys
import os
from urllib.parse import urlencode
from core.config_manager import load_config

# Füge den Root-Pfad zum Python-Path hinzu
root_dir = str(Path(__file__).resolve().parent.parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

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
    """Client für den Vienna WFS Service"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """Initialisiert den WFS Client.
        
        Args:
            config (Optional[Dict[str, Any]]): Direkte Konfiguration für den WFS Client
            config_path (Optional[str]): Pfad zur Konfigurationsdatei
        """
        try:
            # Initialisiere Logger
            self.logger = logging.getLogger(__name__)
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(message)s'))
                self.logger.addHandler(handler)

            # Lade Konfiguration entweder aus Dict oder Datei
            if config is not None:
                self.config = config
                self.logger.info("✅ WFS-Konfiguration aus Dictionary geladen")
            elif config_path is not None:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f).get('vienna_wfs', {})
                self.logger.info(f"✅ WFS-Konfiguration geladen von: {config_path}")
            else:
                raise ValueError("❌ Weder config noch config_path angegeben")

            # Validiere Konfiguration
            if not self.config:
                raise ValueError("❌ Keine gültige WFS-Konfiguration gefunden")

            # Hole WFS URL und validiere
            self.wfs_url = self.config.get('url')
            if not self.wfs_url:
                raise ValueError("❌ Keine WFS-URL in der Konfiguration gefunden")

            # Setze weitere Konfigurationsparameter
            self.version = self.config.get('version', '1.1.0')  # Default auf 1.1.0
            self.timeout = self.config.get('timeout', 30)
            self.streams = self.config.get('streams', [])
            self.srs_name = self.config.get('srsName', 'EPSG:31256')

            self.logger.info(f"""WFS-Konfiguration:
            🔗 URL: {self.wfs_url}
            📦 Version: {self.version}
            ⏱️ Timeout: {self.timeout}
            🗺️ SRS: {self.srs_name}
            📊 Streams: {len(self.streams)}""")

            # Teste Verbindung
            self.wfs = WebFeatureService(
                url=self.wfs_url,
                version=self.version,
                timeout=self.timeout
            )
            
            # Hole verfügbare Layer
            self.available_layers = list(self.wfs.contents.keys())
            self.logger.info(f"✅ WFS-Verbindung erfolgreich. {len(self.available_layers)} Layer verfügbar")

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der WFS-Initialisierung: {str(e)}")
            raise

    def _format_bbox_v11(self, bounds: tuple) -> str:
        """Formatiert BBOX für WFS 1.1.0 Format.
        
        Args:
            bounds: Tuple (min_x, min_y, max_x, max_y)
            
        Returns:
            str: Formatierte BBOX im Format 'minx,miny,maxx,maxy,EPSG:CODE'
        """
        try:
            if len(bounds) != 4:
                raise ValueError("BBOX muss 4 Koordinaten enthalten")
                
            min_x, min_y, max_x, max_y = bounds
            # Formatiere Koordinaten für Vienna WFS (ganzzahlig)
            bbox = f"{int(min_x)},{int(min_y)},{int(max_x)},{int(max_y)},EPSG:31256"
            return bbox
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der BBOX-Formatierung: {str(e)}")
            return None

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

    def fetch_layer(self, layer_name: str, bbox: str = None) -> Optional[gpd.GeoDataFrame]:
        """Holt Daten für einen bestimmten Layer
        
        Args:
            layer_name (str): Name des Layers
            bbox (str, optional): Bounding Box im Format "minx,miny,maxx,maxy,CRS"
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit den Features oder None
        """
        try:
            # Baue WFS URL
            params = {
                'service': 'WFS',
                'version': self.version,
                'request': 'GetFeature',
                'typename': layer_name,
                'srsName': self.srs_name,
                'outputFormat': 'json'
            }
            
            # Füge BBOX hinzu wenn vorhanden
            if bbox:
                params['bbox'] = bbox
                self.logger.info(f"📍 Verwende BBOX: {bbox}")
            
            # Baue URL
            url = f"{self.wfs_url}?{urlencode(params)}"
            self.logger.info(f"🔗 WFS URL: {url}")
            
            # Führe Request aus
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Lade GeoJSON
            data = response.json()
            
            if not data.get('features'):
                self.logger.warning(f"⚠️ Keine Features im GeoJSON für Layer {layer_name}")
                return None
                
            # Konvertiere zu GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(data['features'])
            
            # Setze CRS
            if 'crs' in data:
                gdf.set_crs(data['crs']['properties']['name'], inplace=True)
            else:
                gdf.set_crs(self.srs_name, inplace=True)
                
            self.logger.info(f"✅ {len(gdf)} Features für Layer {layer_name} geladen")
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen von Layer {layer_name}: {str(e)}")
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
            
            if not streams:
                logger.warning("⚠️ Keine Streams in der Konfiguration gefunden")
                return results
                
            logger.info(f"🔄 Verarbeite {len(streams)} Streams...")
            
            for stream in streams:
                layer_name = stream.get('layer')
                if not layer_name:
                    logger.warning(f"⚠️ Kein Layer-Name in Stream gefunden: {stream}")
                    continue
                    
                logger.info(f"🔄 Verarbeite Layer: {layer_name}")
                filters = stream.get('filters', {})
                gdf = self.fetch_layer(layer_name, bbox=bbox, filters=filters)
                
                if gdf is not None and not gdf.empty:
                    logger.info(f"✅ {len(gdf)} Features für Layer {layer_name} geladen")
                    results[stream['name']] = gdf
                else:
                    logger.warning(f"⚠️ Keine Daten für Layer {layer_name} gefunden")
            
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

    def process_streams(self, bbox: Optional[str] = None) -> Dict[str, gpd.GeoDataFrame]:
        """Verarbeitet alle konfigurierten Streams und gibt die Ergebnisse zurück.

        Args:
            bbox: Optionaler Bounding Box String im Format 'minx,miny,maxx,maxy'

        Returns:
            Dictionary mit Layer-Namen als Schlüssel und GeoDataFrames als Werte
        """
        results = {}
        
        if not self.streams:
            self.logger.warning("⚠️ Keine Streams konfiguriert")
            return results
            
        self.logger.info(f"🔄 Verarbeite {len(self.streams)} Streams...")
        
        for stream in self.streams:
            layer_name = stream.get('layer')
            if not layer_name:
                self.logger.warning("⚠️ Stream ohne Layer-Name übersprungen")
                continue
                
            self.logger.info(f"🔄 Verarbeite Layer: {layer_name}")
            
            # Hole Daten für den Layer
            gdf = self.fetch_layer(layer_name, bbox)
            if gdf is None or gdf.empty:
                self.logger.warning(f"⚠️ Keine Daten für Layer {layer_name} gefunden")
                continue
                
            # Wende Mapping an wenn konfiguriert
            if 'mapping' in stream:
                try:
                    gdf = self._apply_mapping(gdf, stream['mapping'])
                    self.logger.info(f"✅ Mapping für Layer {layer_name} angewendet")
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Mapping für Layer {layer_name}: {str(e)}")
                    continue
                    
            results[layer_name] = gdf
            self.logger.info(f"✅ Layer {layer_name} erfolgreich verarbeitet")
            
        return results

    def _apply_mapping(self, gdf: gpd.GeoDataFrame, mapping: Dict[str, Any]) -> gpd.GeoDataFrame:
        """Wendet das Mapping auf die GeoDataFrame an.
        
        Args:
            gdf (gpd.GeoDataFrame): Eingabe GeoDataFrame
            mapping (Dict): Mapping-Konfiguration
            
        Returns:
            gpd.GeoDataFrame: Verarbeiteter GeoDataFrame
        """
        try:
            result_gdf = gdf.copy()
            
            for target_col, mapping_config in mapping.items():
                if 'sources' in mapping_config:
                    # Versuche Daten aus verschiedenen Quellen zu holen
                    for source, source_col in mapping_config['sources'].items():
                        if source_col and source_col in result_gdf.columns:
                            result_gdf[target_col] = result_gdf[source_col]
                            break
                    else:
                        # Wenn keine Quelle gefunden wurde, verwende Default-Wert
                        if 'default' in mapping_config:
                            result_gdf[target_col] = mapping_config['default']
                        else:
                            result_gdf[target_col] = None
                            
                if 'transform' in mapping_config:
                    # Wende Transformation an
                    if mapping_config['transform'] == 'combine_standard':
                        # Kombiniere Gebäudetyp und Baujahr
                        result_gdf[target_col] = result_gdf[source_col].astype(str) + '_' + result_gdf['YEAR'].astype(str)
                    elif mapping_config['transform'] == 'map_building_use':
                        # Mappe Gebäudenutzung
                        result_gdf[target_col] = result_gdf[source_col].map(mapping_config.get('mapping', {}))
            
            return result_gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Mapping: {str(e)}")
            return gdf


def fetch_wfs_data(site_polygon: gpd.GeoDataFrame, layer_name: str, config: Dict) -> Optional[gpd.GeoDataFrame]:
    """Holt WFS-Daten für ein bestimmtes Gebiet und einen Layer.

    Args:
        site_polygon: GeoDataFrame mit dem Standort-Polygon
        layer_name: Name des WFS-Layers
        config: Konfigurationsdaten

    Returns:
        GeoDataFrame mit den WFS-Daten oder None bei Fehler
    """
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"🔄 Hole WFS-Daten für Layer {layer_name}")

        # Prüfe Eingaben
        if site_polygon is None or site_polygon.empty:
            logger.error("❌ Kein gültiges Standort-Polygon übergeben")
            return None

        if not layer_name:
            logger.error("❌ Kein Layer-Name angegeben")
            return None

        if not config:
            logger.error("❌ Keine Konfiguration übergeben")
            return None

        # Hole WFS-Konfiguration
        wfs_config = config.get('vienna_wfs')
        if not wfs_config:
            logger.error("❌ Keine WFS-Konfiguration gefunden")
            return None

        # Erstelle WFS-Client
        wfs = ViennaWFS(wfs_config)
        if not wfs:
            logger.error("❌ WFS-Client konnte nicht erstellt werden")
            return None

        # Konvertiere Polygon zu BBOX
        try:
            bounds = site_polygon.total_bounds
            bbox = ','.join(map(str, bounds))
            logger.info(f"📍 BBOX erstellt: {bbox}")
        except Exception as e:
            logger.error(f"❌ Fehler bei der BBOX-Erstellung: {str(e)}")
            return None

        # Hole Layer-Daten
        try:
            gdf = wfs.fetch_layer(layer_name, bbox)
            if gdf is None or gdf.empty:
                logger.warning(f"⚠️ Keine Daten für Layer {layer_name} gefunden")
                return None

            logger.info(f"✅ {len(gdf)} Features für Layer {layer_name} geladen")
            return gdf

        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Layer-Daten: {str(e)}")
            return None

    except Exception as e:
        logger.error(f"❌ Unerwarteter Fehler: {str(e)}")
        return None


def fetch_wfs_buildings(site_polygon: Optional[gpd.GeoDataFrame] = None) -> Optional[gpd.GeoDataFrame]:
    """Holt Gebäudedaten vom WFS-Server.
    
    Args:
        site_polygon (Optional[gpd.GeoDataFrame]): Optional ein GeoDataFrame mit dem Standort-Polygon
        
    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame mit den Gebäudedaten oder None bei Fehler
    """
    try:
        # Lade Konfiguration
        config = load_config()
        
        # Hole Layer-Name aus der Konfiguration
        layer_name = config.get('wfs', {}).get('building_layer', 'ogdwien:GEBAEUDEGDT')
        
        # Verwende die allgemeine fetch_wfs_data Funktion
        buildings = fetch_wfs_data(site_polygon, layer_name, config)
        
        if buildings is None:
            logger.error("❌ Keine Gebäudedaten vom WFS erhalten")
            return None
            
        logger.info(f"✅ {len(buildings)} Gebäude vom WFS geladen")
        return buildings
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Abrufen der WFS-Gebäudedaten: {str(e)}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("🔎 WFS Daten Test-Modus")
    
    try:
        # Lade Projekt-Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        project_config_path = root_dir / 'cfg' / 'project_config.yml'
        project_config = load_config(project_config_path)
        
        if not project_config:
            raise ValueError("❌ Keine gültige Projekt-Konfiguration gefunden")
            
        # Hole WFS-Konfigurationspfad aus project_config
        wfs_config_path = project_config.get('project', {}).get('config_files', {}).get('wfs', {}).get('config')
        
        if not wfs_config_path:
            raise ValueError("❌ Kein WFS-Konfigurationspfad in project/config_files/wfs/config gefunden")

        # Stelle sicher, dass der Pfad nicht doppelt 'local/' enthält
        wfs_config_path = Path(wfs_config_path)

        # Falls der Pfad mit 'local/' beginnt, entferne es
        if wfs_config_path.parts[0] == 'local':
            wfs_config_path = wfs_config_path.relative_to('local')

        # Konstruiere absoluten Pfad basierend auf root_dir
        wfs_config_path = root_dir / wfs_config_path
        
        logger.info(f"📂 Verwende WFS-Konfiguration: {wfs_config_path}")
        
        # Initialisiere WFS mit Konfiguration
        wfs = ViennaWFS(config_path=str(wfs_config_path))
        
        if wfs.test_connection():
            logging.info("✅ WFS-Test erfolgreich abgeschlossen")
        else:
            logging.error("❌ WFS-Test fehlgeschlagen")
    except Exception as e:
        logging.error(f"❌ Fehler im Test-Modus: {str(e)}")

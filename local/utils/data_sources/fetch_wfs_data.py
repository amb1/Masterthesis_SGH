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

    def fetch_layer(self, layer_name: str, bbox: Optional[tuple] = None) -> Optional[gpd.GeoDataFrame]:
        """Holt Daten für einen bestimmten Layer vom WFS.

        Args:
            layer_name: Name des Layers
            bbox: Optionales Tuple (min_x, min_y, max_x, max_y)

        Returns:
            GeoDataFrame mit den Layer-Daten oder None bei Fehler
        """
        try:
            self.logger.info(f"🔄 Hole Daten für Layer: {layer_name}")
            
            # Baue Filter-Parameter
            filter_params = {
                'service': 'WFS',
                'version': '1.1.0',
                'request': 'GetFeature',
                'typename': layer_name,
                'srsName': 'EPSG:31256',
                'outputFormat': 'json'
            }

            # Füge BBOX hinzu wenn vorhanden
            if bbox is not None and len(bbox) == 4:
                bbox_str = self._format_bbox_v11(bbox)
                if bbox_str:
                    self.logger.info(f"📍 Verwende BBOX: {bbox_str}")
                    filter_params['bbox'] = bbox_str

            # Baue URL
            params = '&'.join([f"{k}={v}" for k, v in filter_params.items()])
            url = f"{self.wfs_url}?{params}"
            self.logger.info(f"🔗 WFS URL: {url}")

            # Hole WFS-Response
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code != 200:
                self.logger.error(f"❌ WFS-Fehler: {response.status_code} - {response.text}")
                return None

            # Parse zu GeoDataFrame
            try:
                gdf = gpd.read_file(io.BytesIO(response.content))
                
                # Prüfe ob Daten vorhanden
                if gdf is None or gdf.empty:
                    self.logger.warning(f"⚠️ Keine Daten im GeoDataFrame für Layer {layer_name}")
                    return None
                    
                # Prüfe Geometrie-Spalte
                if 'geometry' not in gdf.columns:
                    self.logger.error(f"❌ Keine Geometrie-Spalte im GeoDataFrame für Layer {layer_name}")
                    return None
                    
                # Konvertiere OBJECTID zu String wenn vorhanden
                if 'OBJECTID' in gdf.columns:
                    gdf['OBJECTID'] = gdf['OBJECTID'].astype(str)
                
                # Setze CRS wenn nicht gesetzt
                if gdf.crs is None:
                    gdf.set_crs(self.srs_name, inplace=True)
                    
                self.logger.info(f"✅ {len(gdf)} Features für Layer {layer_name} geladen")
                return gdf
                
            except Exception as e:
                self.logger.error(f"❌ Fehler beim Parsen der WFS-Antwort für Layer {layer_name}: {str(e)}")
                return None

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen des Layers {layer_name}: {str(e)}")
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
        """Verarbeitet alle konfigurierten WFS-Streams.

        Args:
            bbox: Optionaler Bounding Box String im Format 'minx,miny,maxx,maxy'

        Returns:
            Dictionary mit Layer-Namen und zugehörigen GeoDataFrames
        """
        results = {}
        
        if not self.streams:
            self.logger.warning("⚠️ Keine Streams konfiguriert")
            return results
            
        self.logger.info(f"🔄 Verarbeite {len(self.streams)} Streams...")
        
        for stream in self.streams:
            try:
                layer_name = stream.get('layer')
                if not layer_name:
                    self.logger.warning(f"⚠️ Kein Layer-Name in Stream definiert: {stream}")
                    continue
                    
                self.logger.info(f"🔄 Verarbeite Layer: {layer_name}")
                
                # Hole Layer-Daten
                gdf = self.fetch_layer(layer_name, bbox)
                
                if gdf is None or gdf.empty:
                    self.logger.warning(f"⚠️ Keine Daten für Layer {layer_name} gefunden")
                    continue
                
                # Wende Mapping an wenn vorhanden
                mapping = stream.get('mapping')
                if mapping:
                    try:
                        # Erstelle Kopie des DataFrames
                        mapped_gdf = gdf.copy()
                        
                        # Wende Mapping auf Spalten an
                        for new_col, old_col in mapping.items():
                            if old_col in gdf.columns:
                                mapped_gdf[new_col] = gdf[old_col]
                            else:
                                self.logger.warning(f"⚠️ Spalte {old_col} nicht in Layer {layer_name} gefunden")
                                
                        gdf = mapped_gdf
                        self.logger.info(f"✅ Mapping für Layer {layer_name} angewendet")
                        
                    except Exception as e:
                        self.logger.error(f"❌ Fehler beim Mapping für Layer {layer_name}: {str(e)}")
                        continue
                
                results[layer_name] = gdf
                self.logger.info(f"✅ Layer {layer_name} erfolgreich verarbeitet")
                
            except Exception as e:
                self.logger.error(f"❌ Fehler bei der Verarbeitung von Stream {stream}: {str(e)}")
                continue
                
        return results


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

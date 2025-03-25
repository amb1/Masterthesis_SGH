"""
WFS Stream Handler für die Verarbeitung von WFS-Streams.
"""

import logging
from typing import Dict, Any, Optional
import geopandas as gpd
from .client import WFSBaseClient

class WFSStreamHandler:
    """Handler für WFS-Streams."""
    
    def __init__(self, client: WFSBaseClient, streams: Dict[str, Any]):
        """Initialisiert den WFS Stream Handler.
        
        Args:
            client: WFS Base Client
            streams: Stream-Konfigurationen
        """
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.streams = streams
        
    def process_streams(self, bbox: Optional[str] = None) -> Dict[str, gpd.GeoDataFrame]:
        """Verarbeitet alle konfigurierten Streams.
        
        Args:
            bbox: Optional[str] - Bounding Box für die Abfrage
            
        Returns:
            Dict[str, gpd.GeoDataFrame]: Dictionary mit Stream-Namen und GeoDataFrames
        """
        results = {}
        
        if not self.streams:
            self.logger.warning("⚠️ Keine Streams konfiguriert")
            return results
            
        for stream_name, stream_config in self.streams.items():
            try:
                # Hole Layer-Name aus Konfiguration
                layer_name = stream_config.get('layer')
                if not layer_name:
                    self.logger.warning(f"⚠️ Kein Layer für Stream {stream_name} konfiguriert")
                    continue
                    
                # Hole Daten vom WFS
                self.logger.info(f"🔄 Verarbeite Stream: {stream_name} (Layer: {layer_name})")
                gdf = self.client.fetch_layer(layer_name, bbox)
                
                if gdf is not None and not gdf.empty:
                    # Füge Stream-spezifische Attribute hinzu
                    gdf['stream_name'] = stream_name
                    gdf['data_source'] = 'wfs'
                    
                    # Füge zu Ergebnissen hinzu
                    results[stream_name] = gdf
                    self.logger.info(f"✅ Stream {stream_name} erfolgreich verarbeitet")
                else:
                    self.logger.warning(f"⚠️ Keine Daten für Stream {stream_name}")
                    
            except Exception as e:
                self.logger.error(f"❌ Fehler bei Stream {stream_name}: {str(e)}")
                continue
                
        return results 
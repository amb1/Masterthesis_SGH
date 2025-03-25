"""
WFS Base Client für grundlegende WFS-Operationen.
"""

from owslib.wfs import WebFeatureService
import geopandas as gpd
from typing import Optional, Dict, Any
import logging
from urllib.parse import urlencode
import requests

class WFSBaseClient:
    """Basis-Client für WFS-Operationen."""
    
    def __init__(self, url: str, version: str = '1.1.0', timeout: int = 30, srs_name: str = 'EPSG:31256'):
        """Initialisiert den WFS Base Client.
        
        Args:
            url: WFS Service URL
            version: WFS Version (default: 1.1.0)
            timeout: Request Timeout in Sekunden (default: 30)
            srs_name: Koordinatensystem (default: EPSG:31256)
        """
        self.logger = logging.getLogger(__name__)
        
        if not url:
            raise ValueError("❌ Keine WFS-URL angegeben")
            
        self.url = url
        self.version = version
        self.timeout = timeout
        self.srs_name = srs_name
        
        # Initialisiere WFS Service
        self.wfs = WebFeatureService(
            url=self.url,
            version=self.version,
            timeout=self.timeout
        )
        
        # Verfügbare Layer
        self.available_layers = list(self.wfs.contents.keys())
        self.logger.info(f"✅ WFS-Verbindung hergestellt. {len(self.available_layers)} Layer verfügbar")
        
    def test_connection(self) -> bool:
        """Testet die WFS-Verbindung.
        
        Returns:
            bool: True wenn Verbindung erfolgreich
        """
        try:
            self.wfs.getcapabilities()
            self.logger.info("✅ WFS-Verbindung erfolgreich getestet")
            return True
        except Exception as e:
            self.logger.error(f"❌ WFS-Verbindungstest fehlgeschlagen: {str(e)}")
            return False
            
    def fetch_layer(self, layer_name: str, bbox: Optional[str] = None) -> Optional[gpd.GeoDataFrame]:
        """Holt Daten für einen Layer.
        
        Args:
            layer_name: Name des Layers
            bbox: Optional[str] - Bounding Box im Format "minx,miny,maxx,maxy,CRS"
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit Features oder None
        """
        try:
            if layer_name not in self.available_layers:
                self.logger.error(f"❌ Layer {layer_name} nicht verfügbar")
                return None
                
            # Baue Request Parameter
            params = {
                'service': 'WFS',
                'version': self.version,
                'request': 'GetFeature',
                'typeName': layer_name,
                'srsName': self.srs_name,
                'outputFormat': 'json'
            }
            
            # Füge BBOX hinzu wenn vorhanden
            if bbox:
                params['bbox'] = bbox
                self.logger.info(f"📍 Verwende BBOX: {bbox}")
            
            # Baue URL und führe Request aus
            url = f"{self.url}?{urlencode(params)}"
            self.logger.debug(f"🔗 WFS URL: {url}")
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Verarbeite Response
            data = response.json()
            if not data.get('features'):
                self.logger.warning(f"⚠️ Keine Features im GeoJSON für Layer {layer_name}")
                return None
                
            # Konvertiere zu GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(data['features'])
            gdf.crs = self.srs_name
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen von Layer {layer_name}: {str(e)}")
            return None 
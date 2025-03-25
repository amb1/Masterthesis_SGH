"""
WFS-Stream-Verarbeitung für große Datenmengen.
"""

import logging
from typing import Dict, Any, Iterator, Optional
import requests
from owslib.wfs import WebFeatureService

logger = logging.getLogger(__name__)

class WFSStream:
    """Klasse für das Streaming von WFS-Daten."""
    
    def __init__(self, url: str, version: str = '2.0.0', page_size: int = 1000):
        """
        Initialisiert den WFS-Stream.
        
        Args:
            url: URL des WFS-Dienstes
            version: WFS-Version
            page_size: Anzahl Features pro Seite
        """
        self.url = url
        self.version = version
        self.page_size = page_size
        self.wfs = WebFeatureService(url=self.url, version=self.version)
        
    def stream_features(self, layer: str, bbox: Optional[str] = None) -> Iterator[Dict[str, Any]]:
        """
        Streamt Features von einem WFS-Layer.
        
        Args:
            layer: Name des WFS-Layers
            bbox: Optional[str] - Bounding Box im Format "minx,miny,maxx,maxy"
            
        Yields:
            Dict: Ein Feature als GeoJSON
        """
        try:
            start_index = 0
            
            while True:
                # Parameter für die Anfrage
                params = {
                    'service': 'WFS',
                    'version': self.version,
                    'request': 'GetFeature',
                    'typeName': layer,
                    'outputFormat': 'application/json',
                    'startIndex': start_index,
                    'count': self.page_size
                }
                
                if bbox:
                    params['bbox'] = bbox
                    
                # Anfrage ausführen
                response = requests.get(self.url, params=params)
                response.raise_for_status()
                
                # Features verarbeiten
                data = response.json()
                features = data.get('features', [])
                
                if not features:
                    break
                    
                for feature in features:
                    yield feature
                    
                start_index += len(features)
                
                # Prüfe ob alle Features abgerufen wurden
                if len(features) < self.page_size:
                    break
                    
        except Exception as e:
            logger.error(f"❌ Fehler beim Streaming der Features: {str(e)}")
            return None 
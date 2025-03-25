"""
WFS-Client für den Zugriff auf WFS-Dienste.
"""

import logging
from typing import Dict, Any, Optional, List
import requests
from owslib.wfs import WebFeatureService
from owslib.fes import PropertyIsEqualTo, And, Or, PropertyIsLike
import json

logger = logging.getLogger(__name__)

class WFSClient:
    """Client für den Zugriff auf WFS-Dienste."""
    
    def __init__(self, url: str, version: str = '2.0.0'):
        """
        Initialisiert den WFS-Client.
        
        Args:
            url: URL des WFS-Dienstes
            version: WFS-Version (default: 2.0.0)
        """
        self.url = url
        self.version = version
        self.wfs = None
        self._connect()
        
    def _connect(self):
        """Verbindung zum WFS-Dienst herstellen."""
        try:
            self.wfs = WebFeatureService(url=self.url, version=self.version)
        except Exception as e:
            logger.error(f"❌ Fehler beim Verbinden mit WFS: {str(e)}")
            raise ConnectionError(f"Konnte keine Verbindung zum WFS-Dienst unter {self.url} herstellen")
            
    def get_features(self, layer: str, bbox: Optional[List[float]] = None, 
                    filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ruft Features von einem WFS-Layer ab.
        
        Args:
            layer: Name des WFS-Layers
            bbox: Bounding Box [minx, miny, maxx, maxy]
            filters: Dictionary mit Filterkriterien
            
        Returns:
            Dict mit Features im GeoJSON-Format
        """
        try:
            # Parameter für die Anfrage
            params = {
                'service': 'WFS',
                'version': self.version,
                'request': 'GetFeature',
                'typeName': layer,
                'outputFormat': 'application/json'
            }
            
            # Bounding Box hinzufügen
            if bbox:
                params['bbox'] = ','.join(map(str, bbox))
                
            # Filter hinzufügen
            if filters:
                filter_parts = []
                for key, value in filters.items():
                    if isinstance(value, (list, tuple)):
                        # OR-Verknüpfung für Listen
                        or_filters = [PropertyIsLike(propertyname=key, literal=str(v)) for v in value]
                        filter_parts.append(Or(or_filters))
                    else:
                        # Einzelner Filter
                        filter_parts.append(PropertyIsEqualTo(propertyname=key, literal=str(value)))
                        
                if len(filter_parts) > 1:
                    params['filter'] = And(filter_parts).toXML()
                else:
                    params['filter'] = filter_parts[0].toXML()
                    
            # Anfrage ausführen
            response = requests.get(self.url, params=params)
            response.raise_for_status()
            
            # GeoJSON parsen
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Features: {str(e)}")
            return {'features': []}
            
    def get_feature_info(self, layer: str) -> Dict[str, Any]:
        """
        Ruft Informationen über einen Layer ab.
        
        Args:
            layer: Name des WFS-Layers
            
        Returns:
            Dict mit Layer-Informationen
        """
        try:
            layer_info = self.wfs.contents[layer]
            return {
                'name': layer_info.id,
                'title': layer_info.title,
                'abstract': layer_info.abstract,
                'bbox': layer_info.boundingBoxWGS84,
                'crs': layer_info.crsOptions,
                'properties': self._get_feature_type_info(layer)
            }
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Layer-Informationen: {str(e)}")
            return {} 

    def _get_feature_type_info(self, layer: str) -> Dict[str, Any]:
        """
        Ruft Informationen über die Eigenschaften eines Feature-Types ab.
        
        Args:
            layer: Name des WFS-Layers
            
        Returns:
            Dict mit Eigenschaftsinformationen
        """
        try:
            # Parameter für DescribeFeatureType
            params = {
                'service': 'WFS',
                'version': self.version,
                'request': 'DescribeFeatureType',
                'typeName': layer,
                'outputFormat': 'application/json'
            }
            
            # Anfrage ausführen
            response = requests.get(self.url, params=params)
            response.raise_for_status()
            
            # Schema parsen
            schema = response.json()
            properties = {}
            
            if 'properties' in schema:
                for prop in schema['properties']:
                    properties[prop['name']] = {
                        'type': prop.get('type'),
                        'description': prop.get('description', ''),
                        'required': prop.get('required', False)
                    }
                    
            return properties
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Feature-Type-Informationen: {str(e)}")
            return {} 
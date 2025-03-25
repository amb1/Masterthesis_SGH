"""
Attributverarbeitung für OSM-Daten.
"""

import logging
from typing import Dict, Any, Optional, List
from .config import OSMConfig

logger = logging.getLogger(__name__)

class OSMAttributeProcessor:
    """Prozessor für OSM-Attribute."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert den Attributprozessor.
        
        Args:
            config: Optionales Konfigurationsobjekt
        """
        self.config = OSMConfig(config)
        self.logger = logging.getLogger(__name__)
        
    def process_building_attributes(self, building_element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Attribute eines OSM-Gebäudes.
        
        Args:
            building_element: OSM-Gebäudeelement
            
        Returns:
            Dictionary mit verarbeiteten Attributen
        """
        try:
            attributes = {
                'data_source': 'osm'
            }
            
            # Name
            if 'name' in building_element:
                attributes['Name'] = building_element['name']
            elif 'addr:street' in building_element and 'addr:housenumber' in building_element:
                attributes['Name'] = f"{building_element['addr:street']} {building_element['addr:housenumber']}"
            
            # Höhe
            if 'height' in building_element:
                try:
                    attributes['height_ag'] = float(building_element['height'])
                except (ValueError, TypeError):
                    pass
                    
            # Geschosse
            if 'building:levels' in building_element:
                try:
                    attributes['floors_ag'] = int(float(building_element['building:levels']))
                except (ValueError, TypeError):
                    pass
                    
            # Gebäudetyp
            if 'building' in building_element:
                attributes['category'] = building_element['building']
                
            return attributes
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Attributverarbeitung: {str(e)}")
            return {'data_source': 'osm'}
            
    def process_street_attributes(self, street_element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Attribute einer OSM-Straße.
        
        Args:
            street_element: OSM-Straßenelement
            
        Returns:
            Dictionary mit verarbeiteten Attributen
        """
        try:
            attributes = {
                'data_source': 'osm'
            }
            
            # Name
            if 'name' in street_element:
                attributes['Name'] = street_element['name']
                
            # Breite
            if 'width' in street_element:
                try:
                    attributes['width'] = float(street_element['width'])
                except (ValueError, TypeError):
                    pass
                    
            # Fahrspuren
            if 'lanes' in street_element:
                try:
                    attributes['lanes'] = int(street_element['lanes'])
                except (ValueError, TypeError):
                    pass
                    
            # Oberfläche
            if 'surface' in street_element:
                attributes['surface'] = street_element['surface']
                
            # Straßentyp
            if 'highway' in street_element:
                highway = street_element['highway']
                if isinstance(highway, list):
                    highway = highway[0]
                attributes['highway'] = highway
                
            return attributes
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Attributverarbeitung: {str(e)}")
            return {'data_source': 'osm'} 
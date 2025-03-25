"""
CityGML-Attribut-Prozessor für die Extraktion von Gebäudeattributen.
"""

import logging
from typing import Dict, Any, Optional
from lxml import etree

class CityGMLAttributeProcessor:
    """Prozessor für CityGML-Attribute."""
    
    def __init__(self, config: Dict[str, Any], namespaces: Dict[str, str]):
        """Initialisiert den Attribut-Prozessor.
        
        Args:
            config: Konfiguration für die Attributextraktion
            namespaces: XML-Namespaces
        """
        self.config = config
        self.namespaces = namespaces
        self.logger = logging.getLogger(__name__)
        
        # Hole Pflichtfelder aus Konfiguration
        self.required_fields = config.get('required_fields', [])
        self.field_config = config.get('citygml_fields', {})
        self.is_wfs = config.get('is_wfs', False)
        
    def extract_building_attributes(self, building: etree._Element) -> Optional[Dict[str, Any]]:
        """Extrahiert alle konfigurierten Attribute eines Gebäudes.
        
        Args:
            building: XML-Element des Gebäudes
            
        Returns:
            Dictionary mit Attributen oder None bei fehlenden Pflichtfeldern
        """
        attributes = {}
        
        # Extrahiere Gebäude-ID
        gml_id = building.get('{' + self.namespaces['gml'] + '}id')
        if gml_id:
            attributes['Name'] = gml_id
            
        # Extrahiere konfigurierte Felder
        for field_name, field_config in self.field_config.items():
            value = self._extract_field_value(building, field_name, field_config)
            if value is not None:  # Nur vorhandene Werte speichern
                attributes[field_name] = value
            
        # Für WFS-Daten: Keine Pflichtfeld-Prüfung
        if self.is_wfs:
            return attributes
            
        # Für CityGML: Prüfe Pflichtfelder
        for field in self.required_fields:
            if field not in attributes or attributes[field] is None:
                self.logger.warning(f"⚠️ Pflichtfeld {field} fehlt für Gebäude {gml_id}")
                return None
                
            # Prüfe ob Fallback-Wert verwendet wurde
            field_config = self.field_config.get(field, {})
            if attributes[field] == field_config.get('fallback'):
                self.logger.warning(f"⚠️ Fallback-Wert für Pflichtfeld {field} verwendet bei Gebäude {gml_id}")
                return None
                
        return attributes
        
    def _extract_field_value(self, building: etree._Element, field_name: str, field_config: Dict[str, Any]) -> Any:
        """Extrahiert einen Feldwert aus dem Gebäude-Element.
        
        Args:
            building: XML-Element des Gebäudes
            field_name: Name des Feldes
            field_config: Konfiguration für das Feld
            
        Returns:
            Extrahierter Wert oder None wenn nicht gefunden
        """
        value = None
        field_type = field_config.get('type', 'str')
        
        # XPath-Extraktion
        if 'xpath' in field_config:
            xpath = field_config['xpath']
            if xpath.startswith('@'):
                # Attribut-Extraktion
                attr_name = xpath[1:]
                if ':' in attr_name:
                    ns, attr = attr_name.split(':')
                    attr_name = '{' + self.namespaces[ns] + '}' + attr
                value = building.get(attr_name)
            else:
                # Element-Extraktion
                element = building.find(xpath, self.namespaces)
                if element is not None:
                    value = element.text if isinstance(element, etree._Element) else element
                
        # Suche nach generischen Attributen
        elif 'search_text' in field_config:
            search_text = field_config['search_text']
            
            # Suche String-Attribute
            string_path = f".//gen:stringAttribute[gen:name='{search_text}']/gen:value"
            string_element = building.find(string_path, self.namespaces)
            if string_element is not None:
                value = string_element.text
                
            # Suche Double-Attribute
            if value is None:
                double_path = f".//gen:doubleAttribute[gen:name='{search_text}']/gen:value"
                double_element = building.find(double_path, self.namespaces)
                if double_element is not None:
                    value = double_element.text
                    
        # Konvertiere Wert in richtigen Typ
        if value is not None:
            try:
                if field_type == 'float':
                    value = float(value)
                elif field_type == 'int':
                    value = int(value)
            except (ValueError, TypeError):
                self.logger.warning(f"⚠️ Konvertierung fehlgeschlagen für {field_name}: {value}")
                value = None
                
        # Verwende Fallback-Wert nur für CityGML
        if not self.is_wfs and value is None and 'fallback' in field_config:
            value = field_config['fallback']
            
        return value 
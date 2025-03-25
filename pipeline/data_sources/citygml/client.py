"""
CityGML-Basis-Client für XML-Verarbeitung.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from lxml import etree

class XMLResolver(etree.Resolver):
    """XML Entity Resolver für häufig verwendete Entities."""
    
    def resolve(self, system_url, public_id, context):
        """Löst XML-Entities auf.
        
        Args:
            system_url: System-URL der Entity
            public_id: Public ID der Entity
            context: Kontext
            
        Returns:
            Aufgelöste Entity oder None
        """
        entities = {
            'uuml': 'ü',
            'auml': 'ä',
            'ouml': 'ö',
            'szlig': 'ß',
            'Auml': 'Ä',
            'Ouml': 'Ö',
            'Uuml': 'Ü'
        }
        
        entity_name = system_url.split(';')[0] if system_url and ';' in system_url else system_url
        if entity_name in entities:
            return self.resolve_string(f'"{entities[entity_name]}"', context)
        return None

class CityGMLBaseClient:
    """Basis-Client für CityGML XML-Verarbeitung."""
    
    def __init__(self, namespaces: Dict[str, str]):
        """Initialisiert den CityGML-Client.
        
        Args:
            namespaces: Dict[str, str] - XML-Namespaces
        """
        self.logger = logging.getLogger(__name__)
        self.namespaces = namespaces
        
        # Initialisiere XML-Parser
        self.parser = etree.XMLParser(resolve_entities=False)
        self.parser.resolvers.add(XMLResolver())
        
    def load_citygml(self, file_path: Path) -> Optional[etree.Element]:
        """Lädt eine CityGML-Datei.
        
        Args:
            file_path: Path - Pfad zur CityGML-Datei
            
        Returns:
            etree.Element: Root-Element oder None bei Fehler
        """
        try:
            self.logger.info(f"🔄 Lade CityGML-Datei: {file_path}")
            tree = etree.parse(str(file_path), parser=self.parser)
            return tree.getroot()
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der CityGML-Datei: {str(e)}")
            return None
            
    def find_buildings(self, root: etree.Element) -> List[etree.Element]:
        """Findet alle Gebäude in einem CityGML-Dokument.
        
        Args:
            root: etree.Element - Root-Element des CityGML-Dokuments
            
        Returns:
            List[etree.Element]: Liste der gefundenen Gebäude
        """
        try:
            buildings = root.findall(".//bldg:Building", self.namespaces)
            self.logger.info(f"✅ {len(buildings)} Gebäude gefunden")
            return buildings
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Suchen der Gebäude: {str(e)}")
            return []
            
    def get_attribute(self, element: etree.Element, xpath: str, default: Any = None) -> Any:
        """Extrahiert ein Attribut mit XPath.
        
        Args:
            element: etree.Element - XML-Element
            xpath: str - XPath-Ausdruck
            default: Any - Standardwert wenn nicht gefunden
            
        Returns:
            Any: Extrahierter Wert oder default
        """
        try:
            result = element.xpath(xpath, namespaces=self.namespaces)
            if not result:
                return default
                
            value = result[0]
            if isinstance(value, str):
                return value.strip()
            elif hasattr(value, 'text'):
                return value.text.strip() if value.text else default
            return value
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Extrahieren von {xpath}: {str(e)}")
            return default
            
    def get_generic_attribute(self, element: etree.Element, name: str, default: Any = None) -> Any:
        """Extrahiert ein generisches Attribut.
        
        Args:
            element: etree.Element - XML-Element
            name: str - Name des Attributs
            default: Any - Standardwert wenn nicht gefunden
            
        Returns:
            Any: Extrahierter Wert oder default
        """
        try:
            # Suche in stringAttribute
            for attr in element.findall(".//gen:stringAttribute", self.namespaces):
                name_elem = attr.find("gen:name", self.namespaces)
                if name_elem is not None and name_elem.text == name:
                    value_elem = attr.find("gen:value", self.namespaces)
                    if value_elem is not None and value_elem.text:
                        return value_elem.text.strip()
                        
            # Suche in doubleAttribute
            for attr in element.findall(".//gen:doubleAttribute", self.namespaces):
                name_elem = attr.find("gen:name", self.namespaces)
                if name_elem is not None and name_elem.text == name:
                    value_elem = attr.find("gen:value", self.namespaces)
                    if value_elem is not None and value_elem.text:
                        return float(value_elem.text.strip())
                        
            return default
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler beim Extrahieren von {name}: {str(e)}")
            return default 
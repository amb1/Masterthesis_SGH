"""
CEA-spezifische Hilfsfunktionen.

Dieses Modul enthält Funktionen für die Verarbeitung und Anreicherung
von Gebäudedaten im CEA-Format.
"""

import random
import pandas as pd
import geopandas as gpd
from typing import Tuple, Dict, Any, Optional, Union, List
from lxml import etree
import logging
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

def get_year_and_suffix(period_str: str, config: Dict[str, Any]) -> Tuple[int, str]:
    """
    Bestimmt das Jahr und den Suffix basierend auf der Bauperiode.
    
    Args:
        period_str: String der Bauperiode (z.B. "1848-1918")
        config: Konfigurationsdaten mit period_ranges und building_periods
        
    Returns:
        tuple: (year, suffix)
    """
    if pd.isna(period_str):
        return 2000, "_I"
        
    # Prüfe das period_ranges Mapping
    period_ranges = config.get('period_ranges', {})
    if period_str in period_ranges:
        start_year, end_year = period_ranges[period_str]
        year = random.randint(start_year, end_year)
    else:
        year = 2000
    
    # Suffix basierend auf dem Jahr bestimmen
    building_periods = config.get('building_periods', [])
    for period in building_periods:
        start = period['start'] if period['start'] is not None else float('-inf')
        end = period['end'] if period['end'] is not None else float('inf')
        if start <= year <= end:
            return year, period['suffix']
            
    return year, "_I"

def adjust_field_widths(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Passt die Feldbreiten für Shapefiles an.
    
    Args:
        gdf: GeoDataFrame mit Gebäudedaten
        
    Returns:
        GeoDataFrame: Angepasstes GeoDataFrame
    """
    adjusted_gdf = gdf.copy()
    
    # Entferne problematische Felder
    fields_to_remove = ['Gebäudemo', 'Gebäudein']
    for field in fields_to_remove:
        if field in adjusted_gdf.columns:
            adjusted_gdf = adjusted_gdf.drop(columns=[field])
    
    return adjusted_gdf

def enrich_building_data(buildings_gdf: gpd.GeoDataFrame, wfs_data: Dict[str, Any]) -> gpd.GeoDataFrame:
    """
    Reichert die Gebäudedaten mit WFS-Daten an.
    
    Args:
        buildings_gdf: GeoDataFrame mit Gebäudedaten
        wfs_data: Dictionary mit WFS-Daten
        
    Returns:
        GeoDataFrame: Angereichertes GeoDataFrame
    """
    enriched_gdf = buildings_gdf.copy()
    
    if not wfs_data:
        return enriched_gdf
    
    # Verarbeite jeden WFS Layer
    for layer_name, layer_data in wfs_data.items():
        if not layer_data or 'features' not in layer_data:
            continue
            
        # Extrahiere Eigenschaften für jedes Gebäude
        for i, row in enriched_gdf.iterrows():
            feature = layer_data['features'][i]
            props = feature.get('properties', {})
            for key, value in props.items():
                enriched_gdf.at[i, f"{layer_name}_{key}"] = value
    
    return enriched_gdf

class CEAMapper:
    """
    Mapper für CEA-Felder aus verschiedenen Datenquellen.
    
    Implementiert die Interface-Regeln aus base/053-interfaces.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den CEA-Mapper.
        
        Args:
            config: Mapping-Konfiguration mit Feldmappings und Validierungsregeln
        """
        self.config = config
        self.validation_rules = config.get("validation", {})
        self.field_mappings = self._load_field_mappings()
        
        # Standard-Namespaces für CityGML
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'bldg2': 'http://www.opengis.net/citygml/building/2.0',
            'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0',
            'core': 'http://www.opengis.net/citygml/2.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0'
        }
        
    def _load_field_mappings(self) -> Dict[str, Any]:
        """
        Lädt die Feldmappings aus der Konfiguration.
        
        Returns:
            Dict[str, Any]: Feldmappings für verschiedene Datenquellen
        """
        try:
            mapping_path = Path(self.config.get('mapping_file', 'config/cea/mapping.yml'))
            if not mapping_path.exists():
                logger.warning(f"⚠️ Mapping-Datei nicht gefunden: {mapping_path}")
                return {}
                
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mappings = yaml.safe_load(f)
                return mappings.get('mappings', {})
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Feldmappings: {str(e)}")
            return {}
            
    def map_field(self, field_name: str, data: Union[dict, etree._Element], source: str) -> Any:
        """
        Mapped ein Feld aus den Quelldaten.
        
        Args:
            field_name: Name des Zielfelds
            data: Quelldaten (Dict für WFS/OSM, XML für CityGML)
            source: Datenquelle ('wfs', 'osm' oder 'citygml')
            
        Returns:
            Any: Gemappter Wert für das Feld
        """
        if field_name not in self.field_mappings:
            return None
            
        mapping = self.field_mappings[field_name]
        source_mapping = mapping.get(source, {})
        
        if source == "citygml":
            return self._map_citygml_field(field_name, data, source_mapping)
        else:
            return self._map_source_field(field_name, data, source_mapping)
            
    def _map_citygml_field(self, field_name: str, xml: etree._Element, mapping: Dict[str, Any]) -> Any:
        """
        Mapped ein Feld aus CityGML-Daten.
        
        Args:
            field_name: Name des Zielfelds
            xml: CityGML XML-Element
            mapping: Mapping-Konfiguration für das Feld
            
        Returns:
            Any: Gemappter Wert
        """
        try:
            # Spezialfall für Name-Generierung
            if field_name == "Name":
                street = self._get_street_name(xml)
                number = self._get_building_number(xml)
                if street and number:
                    return f"{street}_{number}"
                return None
                
            # Spezialfall für REFERENCE
            if field_name == "REFERENCE":
                return xml.get("{http://www.opengis.net/gml}id")
                
            # Normale Feldmappings
            xpath = mapping.get("xpath")
            if not xpath:
                return None
                
            try:
                value = xml.xpath(xpath, namespaces=self.namespaces)
                if value:
                    return self._convert_value(value[0], mapping.get("type", "str"))
            except (IndexError, ValueError):
                pass
                
            return mapping.get("default")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping von CityGML-Feld {field_name}: {str(e)}")
            return None
            
    def _map_source_field(self, field_name: str, data: Dict[str, Any], mapping: Dict[str, Any]) -> Any:
        """
        Mapped ein Feld aus WFS/OSM-Daten.
        
        Args:
            field_name: Name des Zielfelds
            data: Quelldaten als Dictionary
            mapping: Mapping-Konfiguration für das Feld
            
        Returns:
            Any: Gemappter Wert
        """
        try:
            source_field = mapping.get("field")
            if not source_field:
                return None
                
            value = data.get(source_field)
            if value is None:
                return mapping.get("default")
                
            return self._convert_value(value, mapping.get("type", "str"))
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping von Feld {field_name}: {str(e)}")
            return None
            
    def _get_street_name(self, xml: etree._Element) -> Optional[str]:
        """
        Extrahiert den Straßennamen aus CityGML-Daten.
        
        Args:
            xml: CityGML XML-Element
            
        Returns:
            Optional[str]: Straßenname oder None
        """
        try:
            street_queries = [
                ".//xAL:ThoroughfareName/text()",
                ".//xAL:StreetNameElement/text()",
                ".//gen:stringAttribute[@name='street']/gen:value/text()"
            ]
            
            for query in street_queries:
                try:
                    result = xml.xpath(query, namespaces=self.namespaces)
                    if result:
                        return result[0]
                except:
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Extrahieren des Straßennamens: {str(e)}")
            return None
            
    def _get_building_number(self, xml: etree._Element) -> Optional[str]:
        """
        Extrahiert die Hausnummer aus CityGML-Daten.
        
        Args:
            xml: CityGML XML-Element
            
        Returns:
            Optional[str]: Hausnummer oder None
        """
        try:
            number_queries = [
                ".//xAL:BuildingNumber/text()",
                ".//xAL:ThoroughfareNumber/text()",
                ".//gen:stringAttribute[@name='number']/gen:value/text()"
            ]
            
            for query in number_queries:
                try:
                    result = xml.xpath(query, namespaces=self.namespaces)
                    if result:
                        return result[0]
                except:
                    continue
                    
            return None
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Extrahieren der Hausnummer: {str(e)}")
            return None
            
    def _convert_value(self, value: Any, target_type: str) -> Any:
        """
        Konvertiert einen Wert in den Zieltyp.
        
        Args:
            value: Zu konvertierender Wert
            target_type: Zieltyp ('str', 'int', 'float', 'bool')
            
        Returns:
            Any: Konvertierter Wert
        """
        if value is None:
            return None
            
        try:
            if target_type == "int":
                return int(float(value))
            elif target_type == "float":
                return float(value)
            elif target_type == "bool":
                return str(value).lower() in ("true", "1", "yes", "ja")
            else:
                return str(value)
        except (ValueError, TypeError):
            return None
            
    def validate_field(self, field_name: str, value: Any) -> bool:
        """
        Validiert einen Feldwert gegen die definierten Regeln.
        
        Args:
            field_name: Name des Felds
            value: Zu validierender Wert
            
        Returns:
            bool: True wenn der Wert gültig ist
        """
        if field_name not in self.validation_rules:
            return True
            
        rules = self.validation_rules[field_name]
        
        try:
            # Prüfe Minimum
            if "min" in rules and value < rules["min"]:
                logger.warning(f"⚠️ Wert {value} für {field_name} ist kleiner als Minimum {rules['min']}")
                return False
                
            # Prüfe Maximum
            if "max" in rules and value > rules["max"]:
                logger.warning(f"⚠️ Wert {value} für {field_name} ist größer als Maximum {rules['max']}")
                return False
                
            # Prüfe erlaubte Werte
            if "allowed_values" in rules and value not in rules["allowed_values"]:
                logger.warning(f"⚠️ Wert {value} für {field_name} ist nicht in erlaubten Werten {rules['allowed_values']}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Feldvalidierung von {field_name}: {str(e)}")
            return False 
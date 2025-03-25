"""
CEA-spezifische Hilfsfunktionen.

Dieses Modul enthält Funktionen für die Verarbeitung und Anreicherung
von Gebäudedaten im CEA-Format.
"""

import random
import pandas as pd
import geopandas as gpd
from typing import Tuple, Dict, Any, Optional
from lxml import etree

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
    """Mapper für CEA-Gebäudedaten."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den CEA-Mapper.

        Args:
            config: Die Mapping-Konfiguration
        """
        self.config = config
        self.namespaces = {
            'gml': 'http://www.opengis.net/gml',
            'bldg': 'http://www.opengis.net/citygml/building/2.0',
            'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0',
            'core': 'http://www.opengis.net/citygml/2.0',
            'gen': 'http://www.opengis.net/citygml/generics/2.0'
        }

    def map_field(self, field_name: str, citygml_data: Optional[etree._Element] = None,
                  wfs_data: Optional[Dict[str, Any]] = None) -> Any:
        """
        Mappt ein Feld basierend auf den verfügbaren Datenquellen.

        Args:
            field_name: Name des zu mappenden Feldes
            citygml_data: CityGML-Daten als XML-Element
            wfs_data: WFS-Daten als Dictionary

        Returns:
            Der gemappte Wert
        """
        if field_name not in self.config['zone_mappings'] and field_name not in self.config['typology_mappings']:
            return None

        mapping = (self.config['zone_mappings'].get(field_name) or 
                  self.config['typology_mappings'].get(field_name))

        # Verarbeite Mapping-Vererbung
        if 'mapping' in mapping and '_inherit' in mapping['mapping']:
            parent_field = mapping['mapping']['_inherit'].split('.')[0]
            parent_mapping = (self.config['zone_mappings'].get(parent_field) or 
                            self.config['typology_mappings'].get(parent_field))
            if parent_mapping and 'mapping' in parent_mapping:
                mapping['mapping'].update(parent_mapping['mapping'])
                del mapping['mapping']['_inherit']

        # Prüfe Datenquellen in der konfigurierten Reihenfolge
        for source in self.config['data_source_priority']:
            if source == 'citygml' and citygml_data is not None:
                value = self._map_citygml_field(mapping, citygml_data)
                if value is not None:
                    return self._transform_value(value, mapping)
            elif source == 'wfs' and wfs_data is not None:
                value = self._map_wfs_field(mapping, wfs_data)
                if value is not None:
                    return self._transform_value(value, mapping)

        # Wenn kein Wert gefunden wurde, verwende den Default-Wert
        return mapping.get('default')

    def _map_citygml_field(self, mapping: Dict[str, Any], data: etree._Element) -> Optional[Any]:
        """Mappt ein Feld aus CityGML-Daten."""
        if 'sources' not in mapping or 'citygml' not in mapping['sources']:
            return None

        citygml_source = mapping['sources']['citygml']
        
        # Spezialbehandlung für Name-Feld
        if mapping.get('transform') == 'combine_address':
            street = data.xpath(".//xAL:ThoroughfareName/text()", namespaces=self.namespaces)
            number = data.xpath(".//xAL:ThoroughfareNumber/text()", namespaces=self.namespaces)
            if street and number:
                return f"{street[0]}_{number[0]}"
            return mapping.get('default', 'Unknown')

        # Spezialbehandlung für Höhe und Geschosse
        if citygml_source == 'bldg:measuredHeight':
            value = data.xpath(".//bldg:measuredHeight/text()", namespaces=self.namespaces)
            if value:
                return float(value[0])
        elif citygml_source == 'bldg:storeysAboveGround':
            value = data.xpath(".//bldg:storeysAboveGround/text()", namespaces=self.namespaces)
            if value:
                return int(value[0])

        # Spezialbehandlung für Adressfelder
        if citygml_source in ['ThoroughfareName', 'ThoroughfareNumber', 'PostalCodeNumber']:
            xpath_map = {
                'ThoroughfareName': ".//xAL:ThoroughfareName/text()",
                'ThoroughfareNumber': ".//xAL:ThoroughfareNumber/text()",
                'PostalCodeNumber': ".//xAL:PostalCodeNumber/text()"
            }
            value = data.xpath(xpath_map[citygml_source], namespaces=self.namespaces)
            if value:
                return value[0]

        # Spezialbehandlung für REFERENCE
        if citygml_source == '@gml:id':
            value = data.get('{http://www.opengis.net/gml}id')
            if value:
                return value

        if isinstance(citygml_source, list):
            values = []
            for xpath in citygml_source:
                try:
                    value = data.xpath(xpath, namespaces=self.namespaces)
                    if value:
                        values.append(value[0])
                    else:
                        values.append('')
                except Exception:
                    values.append('')
            
            if all(v == '' for v in values):
                return mapping.get('default')
            
            if 'format' in mapping:
                return mapping['format'].format(*values)
            return values[0] if len(values) == 1 else values

        return mapping.get('default')

    def _map_wfs_field(self, mapping: Dict[str, Any], data: Dict[str, Any]) -> Optional[Any]:
        """Mappt ein Feld aus WFS-Daten."""
        if 'sources' not in mapping or 'wfs' not in mapping['sources']:
            return None

        wfs_source = mapping['sources']['wfs']
        if isinstance(wfs_source, dict):
            # Für zusammengesetzte Felder (z.B. Adresse)
            values = {}
            for key, field in wfs_source.items():
                values[key] = data.get(field, '')
            if all(v != '' for v in values.values()):
                if 'format' in mapping:
                    return mapping['format'].format(**values)
                return values
        else:
            # Für einfache Felder
            return data.get(wfs_source)

        return None

    def _transform_value(self, value: Any, mapping: Dict[str, Any]) -> Any:
        """Transformiert einen Wert basierend auf der Mapping-Konfiguration."""
        if value is None:
            return mapping.get('default')

        # Wenn ein Mapping definiert ist, wende es direkt an
        if 'mapping' in mapping:
            return mapping['mapping'].get(str(value), mapping.get('default'))

        if 'transform' not in mapping:
            return value

        transform = mapping['transform']
        if transform == 'to_int':
            try:
                return int(value)
            except (ValueError, TypeError):
                return mapping.get('default')
        elif transform == 'to_float':
            try:
                return float(value)
            except (ValueError, TypeError):
                return mapping.get('default')
        elif transform == 'combine_address':
            if isinstance(value, dict):
                return mapping['format'].format(**value)
            elif isinstance(value, list):
                return mapping['format'].format(*value)
            return value
        elif transform == 'none':
            # Wenn ein Mapping definiert ist, wende es nach der Transformation an
            if 'mapping' in mapping:
                return mapping['mapping'].get(str(value), mapping.get('default'))
            return value

        return value

    def validate_field(self, field_name: str, value: Any) -> bool:
        """
        Validiert einen Feldwert gegen die definierten Regeln.

        Args:
            field_name: Name des Feldes
            value: Zu validierender Wert

        Returns:
            True wenn valid, False sonst
        """
        mapping = (self.config['zone_mappings'].get(field_name) or 
                  self.config['typology_mappings'].get(field_name))
        
        if not mapping:
            return True

        # Prüfe ob das Feld required ist
        if mapping.get('required', False) and value is None:
            raise ValueError(f"Feld {field_name} ist erforderlich, aber kein Wert vorhanden")

        return True 
"""
CEA-spezifische Hilfsfunktionen für das Mapping von Gebäudedaten.
"""

import random
import pandas as pd
import geopandas as gpd
from typing import Tuple, Dict, Any, Optional, Union, List
from lxml import etree
import logging
from pathlib import Path
import yaml
import numpy as np
import os

from .building_classifier import BuildingClassifier

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

def enrich_building_data(gdf: gpd.GeoDataFrame, wfs_data: Dict[str, Any]) -> gpd.GeoDataFrame:
    """
    Reichert GeoDataFrame mit WFS-Daten an.
    
    Args:
        gdf: GeoDataFrame mit Gebäudedaten
        wfs_data: WFS-Daten als Dictionary
        
    Returns:
        gpd.GeoDataFrame: Angereicherter GeoDataFrame
    """
    try:
        if not wfs_data or 'Gebäudeinfo' not in wfs_data:
            return gdf
            
        features = wfs_data['Gebäudeinfo'].get('features', [])
        if not features:
            return gdf
            
        # Extrahiere Properties aus Features
        for i, feature in enumerate(features):
            if not feature or 'properties' not in feature:
                continue
                
            properties = feature['properties']
            if not properties:
                continue
                
            # Füge Properties zum GeoDataFrame hinzu
            for key, value in properties.items():
                gdf.at[i, f'Gebäudeinfo_{key}'] = value
                
        return gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Datenanreicherung: {str(e)}")
        return gdf

class CEAMapper:
    """Klasse für das Mapping von Gebäudedaten auf CEA-Attribute."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den CEA-Mapper.
        
        Args:
            config: Mapping-Konfiguration
        """
        self.config = config
        self.cea_mappings = config.get('cea_mappings', {})
        
    def create_zone_file(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Erstellt die zone.shp Datei.
        
        Args:
            gdf: GeoDataFrame mit Gebäudedaten
            
        Returns:
            gpd.GeoDataFrame: GeoDataFrame im zone.shp Format
        """
        try:
            # Erstelle neuen GeoDataFrame für zone.shp
            zone_gdf = gpd.GeoDataFrame(geometry=gdf.geometry)
            
            # Hole zone-Mappings aus Konfiguration
            zone_mappings = self.cea_mappings.get('zone', {})
            
            # Mappe Felder gemäß Konfiguration
            for cea_field, mapping in zone_mappings.items():
                sources = mapping.get('sources', {})
                
                # WFS-Mapping
                if 'wfs' in sources:
                    wfs_mapping = sources['wfs']
                    format_str = sources.get('format')
                    
                    if format_str:
                        # Hole Werte für das Format
                        values = {}
                        for key, field in wfs_mapping.items():
                            values[key] = gdf[field]
                            
                        # Wende Format an
                        zone_gdf[cea_field] = [format_str.format(**{k: row[v] for k, v in wfs_mapping.items()}) 
                                             for _, row in gdf.iterrows()]
                    else:
                        # Direktes Mapping ohne Format
                        field = next(iter(wfs_mapping.values()))
                        zone_gdf[cea_field] = gdf[field]
                        
            return zone_gdf
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen der zone.shp: {str(e)}")
            return gdf
            
    def create_typology_file(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Erstellt die typology.shp Datei.
        
        Args:
            gdf: GeoDataFrame mit Gebäudedaten
            
        Returns:
            gpd.GeoDataFrame: Gemappte Daten für typology.shp
        """
        try:
            result = gdf.copy()
            
            # Mappe jedes Gebäude
            for idx, row in result.iterrows():
                data = row.to_dict()
                
                # Name aus Straße und Hausnummer
                street = self._get_value(data, self.config["cea_mappings"]["typology"]["Name"]["sources"]["wfs"]["street"])
                house_no = self._get_value(data, self.config["cea_mappings"]["typology"]["Name"]["sources"]["wfs"]["number"])
                result.at[idx, "Name"] = f"{street}_{house_no}"
                
                # Baujahr und Standard
                result.at[idx, "YEAR"] = self._get_value(data, self.config["cea_mappings"]["typology"]["YEAR"])
                result.at[idx, "STANDARD"] = self._get_standard(data)
                
                # Nutzungstypen
                result.at[idx, "1ST_USE"] = self._get_use_type(data)
                result.at[idx, "1ST_USE_R"] = 1
                result.at[idx, "2ND_USE"] = ""
                result.at[idx, "2ND_USE_R"] = 0
                result.at[idx, "3RD_USE"] = ""
                result.at[idx, "3RD_USE_R"] = 0
                
                # Referenz
                result.at[idx, "REFERENCE"] = self._get_value(data, self.config["cea_mappings"]["typology"]["REFERENCE"])
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen der typology.shp: {str(e)}")
            return gdf
            
    def _get_value(self, data: Dict, field_config: Dict) -> str:
        """
        Extrahiert einen Wert aus den Daten basierend auf der Feldkonfiguration.
        
        Args:
            data: Dictionary mit Gebäudedaten
            field_config: Konfiguration für das Feld
            
        Returns:
            str: Der extrahierte Wert
        """
        if not field_config:
            return ""
            
        # Default-Wert zurückgeben, wenn konfiguriert
        if "default" in field_config:
            return str(field_config["default"])
            
        # Wenn keine sources definiert sind
        if "sources" not in field_config:
            return ""
            
        sources = field_config["sources"]
        
        # Wenn WFS-Quellen als Liste definiert sind
        if isinstance(sources.get("wfs"), list):
            for field in sources["wfs"]:
                if field in data and data[field]:
                    return str(data[field])
            return ""
            
        # Wenn WFS-Quellen als Dictionary mit Format definiert sind
        if isinstance(sources.get("wfs"), dict) and "format" in sources:
            format_str = sources["format"]
            format_values = {}
            
            for key, field in sources["wfs"].items():
                format_values[key] = str(data.get(field, ""))
                
            try:
                return format_str.format(**format_values)
            except KeyError:
                return ""
                
        # Einzelne WFS-Quelle
        if isinstance(sources.get("wfs"), str):
            return str(data.get(sources["wfs"], ""))
            
        return ""
            
    def _get_floors_ag(self, data: Dict) -> int:
        """Bestimmt die Anzahl der Stockwerke über Grund."""
        try:
            # Versuche direkt GESCH_ANZ
            floors = data.get("GEBAEUDEINFOOGD_GESCH_ANZ")
            if floors is not None:
                return int(floors)
                
            # Alternativ aus Höhe berechnen
            height = data.get("measuredHeight")
            if height is not None:
                return max(1, int(float(height) / 3.0))
                
            return 1  # Fallback
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Stockwerkbestimmung: {str(e)}")
            return 1
            
    def _get_height_ag(self, data: Dict) -> float:
        """Bestimmt die Gebäudehöhe über Grund."""
        try:
            # Versuche measuredHeight
            height = data.get("measuredHeight")
            if height is not None:
                return float(height)
                
            # Alternativ HoeheDach
            height = data.get("HoeheDach")
            if height is not None:
                return float(height)
                
            # Fallback: Berechnung aus Stockwerken
            floors = self._get_floors_ag(data)
            return float(floors * 3.0)
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Höhenbestimmung: {str(e)}")
            return 3.0
            
    def _get_standard(self, data: Dict) -> str:
        """Generiert den STANDARD-Wert für ein Gebäude."""
        try:
            # Bestimme Gebäudetyp-Präfix
            building_type = data.get("Gebäudeinfo_L_NUTZUNG", "")
            prefix = self.config["wfs"]["vienna"]["building_types"]["standard_prefix"].get(building_type, "AB")
            
            # Bestimme Perioden-Suffix
            suffix = self._get_period_suffix(data)
            
            return f"{prefix}_{suffix}"
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der STANDARD-Generierung: {str(e)}")
            return "NONE_X"
            
    def _get_period_suffix(self, data: Dict) -> str:
        """Bestimmt den Perioden-Suffix."""
        try:
            # Versuche exaktes Jahr
            year = data.get("Gebäudeinfo_BAUJAHR")
            if year is not None:
                return self._map_year_to_period(int(year))
                
            return "X"  # Fallback
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Suffix-Bestimmung: {str(e)}")
            return "X"
            
    def _map_year_to_period(self, year: int) -> str:
        """Mappt ein Jahr auf eine Periode."""
        try:
            periods = self.config["wfs"]["vienna"]["building_periods"]
            
            for period in periods:
                start = period["start"] if period["start"] is not None else float('-inf')
                end = period["end"] if period["end"] is not None else float('inf')
                
                if start <= year <= end:
                    return period["suffix"].replace("_", "")
                    
            return "X"
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Jahr-Mapping: {str(e)}")
            return "X"
            
    def _get_use_type(self, data: Dict) -> str:
        """Bestimmt den Gebäudenutzungstyp."""
        try:
            building_type = data.get("Gebäudeinfo_L_NUTZUNG", "")
            return self.config["wfs"]["vienna"]["building_types"]["use_type"].get(building_type, "RESIDENTIAL")
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Nutzungsbestimmung: {str(e)}")
            return "RESIDENTIAL"

    def validate_field(self, field_name, value):
        """Validiert ein gemapptes Feld."""
        field_config = self.field_mappings.get(field_name)
        if not field_config:
            return True

        # Prüfe ob das Feld erforderlich ist
        if field_config.get('required', False) and value is None:
            raise ValueError(f"Feld {field_name} ist erforderlich, aber kein Wert vorhanden")

        return True 
"""
CEA-spezifische Hilfsfunktionen.

Dieses Modul enthält Funktionen für die Verarbeitung und Anreicherung
von Gebäudedaten im CEA-Format.
"""

import random
import pandas as pd
import geopandas as gpd
from typing import Tuple, Dict, Any, Optional

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
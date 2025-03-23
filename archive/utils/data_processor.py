"""
Datenverarbeitungsmodul für CEA-Projekte.

Dieses Modul enthält Funktionen zur Verarbeitung und Transformation von Gebäudedaten,
einschließlich CityGML, OSM und WFS-Daten.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import geopandas as gpd
import pandas as pd
from simpledbf import Dbf5

from .data_sources.fetch_citygml_buildings import fetch_citygml_buildings, CityGMLBuildingProcessor as CityGMLFetcher
from .data_sources.fetch_osm_buildings import (
    fetch_surrounding_buildings,
    process_osm_buildings,
    save_surrounding_buildings,
    fetch_osm_buildings
)
from .data_sources.fetch_osm_streets import fetch_osm_streets
from .data_sources.fetch_wfs_data import ViennaWFS
from .data_processing.cea_building_processor import CEABuildingProcessor
from .data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from .transformations import transform_value

# Logger konfigurieren
logger = logging.getLogger(__name__)

def process_building_data(scenario_path: Path, config: Dict) -> Tuple[gpd.GeoDataFrame, List[Dict]]:
    """Verarbeitet Gebäudedaten aus verschiedenen Quellen
    
    Args:
        scenario_path: Pfad zum Szenarioverzeichnis
        config: Konfigurationsdaten
        
    Returns:
        Tuple[gpd.GeoDataFrame, List[Dict]]: (Verarbeitete Gebäudedaten, Liste der Fehler)
    """
    errors = []
    
    try:
        # CityGML Gebäude laden
        citygml_processor = CityGMLFetcher(config['citygml'])
        buildings_gdf = fetch_citygml_buildings(citygml_processor)
        
        if buildings_gdf.empty:
            errors.append({
                'source': 'CityGML',
                'error': 'Keine Gebäude gefunden'
            })
            return gpd.GeoDataFrame(), errors
            
        # WFS-Daten laden
        wfs = ViennaWFS(config['wfs'])
        wfs_data = wfs.fetch_building_data(buildings_gdf)
        
        if wfs_data.empty:
            errors.append({
                'source': 'WFS',
                'error': 'Keine WFS-Daten gefunden'
            })
        
        # Gebäudedaten anreichern
        cea_processor = CEABuildingProcessor(config['cea'])
        enriched_buildings = cea_processor.process_buildings(buildings_gdf, wfs_data)
        
        # Umgebungsgebäude laden
        surroundings = fetch_surrounding_buildings(
            buildings_gdf,
            config['osm']['buffer_distance']
        )
        
        if surroundings.empty:
            errors.append({
                'source': 'OSM',
                'error': 'Keine Umgebungsgebäude gefunden'
            })
        
        # Straßendaten laden
        streets = fetch_osm_streets(
            buildings_gdf,
            config['osm']['buffer_distance']
        )
        
        if streets.empty:
            errors.append({
                'source': 'OSM',
                'error': 'Keine Straßendaten gefunden'
            })
        
        # Ergebnisse speichern
        save_results(
            scenario_path,
            enriched_buildings,
            surroundings,
            streets
        )
        
        return enriched_buildings, errors
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Gebäudedatenverarbeitung: {str(e)}")
        errors.append({
            'source': 'Verarbeitung',
            'error': str(e)
        })
        return gpd.GeoDataFrame(), errors

def save_results(
    scenario_path: Path,
    buildings: gpd.GeoDataFrame,
    surroundings: gpd.GeoDataFrame,
    streets: gpd.GeoDataFrame
) -> bool:
    """Speichert die verarbeiteten Daten
    
    Args:
        scenario_path: Pfad zum Szenarioverzeichnis
        buildings: Verarbeitete Gebäudedaten
        surroundings: Umgebungsgebäude
        streets: Straßendaten
        
    Returns:
        bool: True wenn erfolgreich, False sonst
    """
    try:
        # Speicherpfade
        geometry_path = scenario_path / 'inputs/building-geometry'
        properties_path = scenario_path / 'inputs/building-properties'
        networks_path = scenario_path / 'inputs/networks'
        
        # Gebäudedaten speichern
        buildings.to_file(geometry_path / 'zone.shp')
        
        # Umgebungsgebäude speichern
        if not surroundings.empty:
            surroundings.to_file(geometry_path / 'surroundings.shp')
            
        # Straßendaten speichern
        if not streets.empty:
            streets.to_file(networks_path / 'streets.shp')
            
        # Gebäudetypologie speichern
        typology = buildings[['building_id', 'building_type', 'construction_year']]
        dbf = Dbf5(properties_path / 'typology.dbf')
        dbf.write(typology)
        
        # Site-Polygon erstellen und speichern
        site_polygon = create_site_polygon(buildings)
        save_site_polygon(site_polygon, geometry_path / 'site.shp')
        
        logger.info("✅ Ergebnisse erfolgreich gespeichert")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Ergebnisse: {str(e)}")
        return False

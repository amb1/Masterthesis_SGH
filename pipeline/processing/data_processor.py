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

from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings, CityGMLBuildingProcessor as CityGMLFetcher
from pipeline.data_sources.osm_building_fetcher import (
    fetch_surrounding_buildings,
    process_osm_buildings,
    save_surrounding_buildings,
    fetch_osm_buildings
)
from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
from pipeline.data_sources.wfs_fetcher import ViennaWFS
from pipeline.processing.cea_processor import CEABuildingProcessor
from pipeline.geometry.site_polygon import create_site_polygon, save_site_polygon
from core.project_paths import ProjectPaths

# Logger konfigurieren
logger = logging.getLogger(__name__)

def process_building_data(project_paths: ProjectPaths, config: Dict) -> Tuple[gpd.GeoDataFrame, List[Dict]]:
    """Verarbeitet Gebäudedaten aus verschiedenen Quellen
    
    Args:
        project_paths: ProjectPaths Instanz für Pfadverwaltung
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
                'message': 'Keine Gebäude gefunden'
            })
            return buildings_gdf, errors
            
        # Rohdaten speichern
        raw_buildings_path = project_paths.get_data_path('raw') / 'buildings_raw.gpkg'
        buildings_gdf.to_file(raw_buildings_path, driver='GPKG')
        logger.info(f"✅ Rohe Gebäudedaten gespeichert: {raw_buildings_path}")
            
        # CEA-Prozessor initialisieren
        cea_processor = CEABuildingProcessor(config)
        
        # Gebäude verarbeiten
        buildings_gdf = cea_processor.process_buildings(buildings_gdf)
        
        # Verarbeitete Daten speichern
        processed_buildings_path = project_paths.get_data_path('processed') / 'buildings_processed.gpkg'
        buildings_gdf.to_file(processed_buildings_path, driver='GPKG')
        logger.info(f"✅ Verarbeitete Gebäudedaten gespeichert: {processed_buildings_path}")
        
        # Site-Polygon erstellen
        site_polygon = create_site_polygon(buildings_gdf)
        save_site_polygon(site_polygon, project_paths.get_data_path('processed'))
        
        # Umgebungsgebäude laden
        surroundings_gdf = fetch_surrounding_buildings(site_polygon, config)
        if not surroundings_gdf.empty:
            # Rohe Umgebungsdaten speichern
            raw_surroundings_path = project_paths.get_data_path('raw') / 'surroundings_raw.gpkg'
            surroundings_gdf.to_file(raw_surroundings_path, driver='GPKG')
            
            surroundings_gdf = process_osm_buildings(surroundings_gdf)
            
            # Verarbeitete Umgebungsdaten speichern
            processed_surroundings_path = project_paths.get_data_path('processed') / 'surroundings_processed.gpkg'
            surroundings_gdf.to_file(processed_surroundings_path, driver='GPKG')
        
        # Straßen laden
        streets_gdf = fetch_osm_streets(site_polygon)
        if not streets_gdf.empty:
            # Straßendaten speichern
            streets_path = project_paths.get_data_path('processed') / 'streets.gpkg'
            streets_gdf.to_file(streets_path, driver='GPKG')
        
        # WFS-Daten laden
        wfs = ViennaWFS(config)
        wfs_data = wfs.fetch_data()
        
        # Ergebnisse für CEA speichern
        save_cea_results(project_paths, buildings_gdf, surroundings_gdf, streets_gdf)
        
        return buildings_gdf, errors
        
    except Exception as e:
        logger.error(f"Fehler bei der Verarbeitung der Gebäudedaten: {str(e)}")
        errors.append({
            'source': 'Verarbeitung',
            'message': str(e)
        })
        return gpd.GeoDataFrame(), errors

def save_cea_results(
    project_paths: ProjectPaths,
    buildings: gpd.GeoDataFrame,
    surroundings: gpd.GeoDataFrame,
    streets: gpd.GeoDataFrame
) -> bool:
    """Speichert die verarbeiteten Daten im CEA-Format
    
    Args:
        project_paths: ProjectPaths Instanz für Pfadverwaltung
        buildings: Verarbeitete Gebäudedaten
        surroundings: Umgebungsgebäude
        streets: Straßendaten
        
    Returns:
        bool: True wenn erfolgreich gespeichert
    """
    try:
        # Speicherpfade definieren
        buildings_path = project_paths.get_cea_path('building-geometry') / "zone.shp"
        surroundings_path = project_paths.get_cea_path('building-geometry') / "surroundings.shp"
        streets_path = project_paths.get_cea_path('networks') / "streets.shp"
        
        # Daten speichern
        buildings.to_file(buildings_path)
        if not surroundings.empty:
            surroundings.to_file(surroundings_path)
        if not streets.empty:
            streets.to_file(streets_path)
            
        # Kopie der finalen Daten im results-Verzeichnis
        results_dir = project_paths.get_data_path('results')
        buildings.to_file(results_dir / "zone.gpkg", driver='GPKG')
        if not surroundings.empty:
            surroundings.to_file(results_dir / "surroundings.gpkg", driver='GPKG')
        if not streets.empty:
            streets.to_file(results_dir / "streets.gpkg", driver='GPKG')
            
        logger.info("✅ Alle Daten erfolgreich gespeichert")
        return True
        
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Daten: {str(e)}")
        return False 
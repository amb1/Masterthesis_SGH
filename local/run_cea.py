import argparse
from pathlib import Path
import yaml
import sys
import os
import pandas as pd
import geopandas as gpd
from simpledbf import Dbf5
import time
from shapely.geometry import Point
import logging

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent
sys.path.append(str(local_dir))

from utils.data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings, CityGMLBuildingProcessor as CityGMLFetcher
from utils.data_sources.fetch_osm_buildings import fetch_surrounding_buildings, process_osm_buildings, save_surrounding_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_sources.fetch_wfs_data import ViennaWFS as WFSFetcher
from utils.data_processing.config_loader import load_config

def get_project_info(args=None):
    """
    Holt Projekt- und Szenarioinformationen entweder aus Argumenten oder interaktiv
    
    Args:
        args: Argparse Namespace mit project_name und scenario_name (optional)
    """
    if args and args.project_name and args.scenario_name:
        project_name = args.project_name
        scenario_name = args.scenario_name
    else:
        print("\nProjektinformationen eingeben:")
        project_name = input("Projektname: ").strip()
        
        # Zeige existierende Szenarien für das Projekt
        project_path = Path("projects") / project_name
        if project_path.exists():
            existing_scenarios = [d.name for d in project_path.iterdir() if d.is_dir()]
            if existing_scenarios:
                print(f"\nExistierende Szenarien für {project_name}:")
                for scenario in existing_scenarios:
                    print(f"- {scenario}")
        
        scenario_name = input("Szenarioname: ").strip()
    
    # Validiere Eingaben
    if not project_name or not scenario_name:
        raise ValueError("Projekt- und Szenarioname müssen angegeben werden!")
    
    # Erstelle Pfade
    project_path = Path("projects") / project_name
    scenario_path = project_path / scenario_name
    
    # Überprüfe ob Szenario bereits existiert
    if scenario_path.exists():
        if args and args.force:
            choice = 'y'
        else:
            choice = input(f"\nSzenario '{scenario_name}' existiert bereits. Überschreiben? (y/n): ").lower()
        
        if choice != 'y':
            print("Abbruch.")
            sys.exit(0)
    
    return project_name, scenario_name, project_path, scenario_path

def setup_project_structure(project_path: Path, scenario_path: Path) -> dict:
    """Erstellt die CEA-Projektstruktur"""
    try:
        # Erstelle Verzeichnisstruktur
        dirs = {
            'inputs': {
                'building-geometry': ['zone.shp', 'site.shp', 'surroundings.shp'],
                'building-properties': ['typology.dbf'],
                'networks': ['streets.shp']
            },
            'outputs': {
                'data': ['zone_enriched.geojson']
            }
        }
        
        # Erstelle Verzeichnisse
        for parent, children in dirs.items():
            parent_path = scenario_path / parent
            parent_path.mkdir(parents=True, exist_ok=True)
            
            for child, files in children.items():
                child_path = parent_path / child
                child_path.mkdir(parents=True, exist_ok=True)
                
                # Erstelle leere Dateien
                for file in files:
                    file_path = child_path / file
                    if not file_path.exists():
                        file_path.touch()
        
        return {
            'project': project_path,
            'scenario': scenario_path,
            'geometry': scenario_path / 'inputs' / 'building-geometry',
            'properties': scenario_path / 'inputs' / 'building-properties',
            'networks': scenario_path / 'inputs' / 'networks',
            'outputs': scenario_path / 'outputs' / 'data'
        }
        
    except Exception as e:
        print(f"❌ Fehler beim Erstellen der Projektstruktur: {str(e)}")
        raise

def main():
    """Hauptfunktion für den CEA-Workflow"""
    try:
        # Lade Konfigurationen
        config = load_configs()
        
        # Hole Projektinformationen
        project_name, scenario_name, project_path, scenario_path = get_project_info()
        
        # Erstelle Projektstruktur
        project_dir = setup_project_structure(project_path, scenario_path)
        
        # Initialisiere WFS Service einmalig
        wfs_config = {'vienna_wfs': config['wfs']}  # Korrigiere Konfigurationsstruktur
        wfs_fetcher = WFSFetcher(wfs_config)
        
        # Hole initiale Gebäudedaten mit einer großzügigen Bounding Box für Wien
        logger.info("🔄 Hole initiale Gebäudedaten...")
        initial_bbox = [16.2264, 48.1182, 16.5775, 48.3231]  # Temporäre Box für ersten Abruf
        buildings_gdf = wfs_fetcher.fetch_building_model(initial_bbox)
        
        if buildings_gdf is None or buildings_gdf.empty:
            raise ValueError("❌ Keine Gebäude im Suchbereich gefunden!")
        
        # Erstelle Site Polygon
        logger.info("📐 Erstelle Site-Polygon...")
        site_polygon = create_site_polygon(buildings_gdf)
        site_path = project_dir['geometry'] / 'site.shp'
        save_site_polygon(site_polygon, site_path)
        
        # Verwende die präzise Bounding Box aus dem Site-Polygon
        bbox = site_polygon.total_bounds
        logger.info(f"📍 Verwende präzise Bounding Box: {bbox}")
        
        # Hole die finalen Gebäudedaten
        logger.info("🔄 Hole finale Gebäudedaten...")
        buildings_gdf = wfs_fetcher.fetch_building_model(bbox)
        
        if buildings_gdf is None or buildings_gdf.empty:
            raise ValueError("❌ Keine Gebäude im finalen Suchbereich gefunden!")
        
        # Hole Umgebungsgebäude
        logger.info("🏘️ Hole Umgebungsgebäude...")
        surroundings_gdf = fetch_surrounding_buildings(site_polygon, config['osm'])
        surroundings_gdf = process_osm_buildings(surroundings_gdf, config['osm']['building_defaults'])
        surroundings_path = project_dir['geometry'] / 'surroundings.shp'
        save_surrounding_buildings(surroundings_gdf, surroundings_path)
        
        # Hole Straßendaten
        logger.info("🛣️ Hole Straßendaten...")
        streets_gdf = fetch_osm_streets(site_polygon, config['osm']['street_tags'])
        streets_path = project_dir['networks'] / 'streets.shp'
        streets_gdf.to_file(streets_path)
        
        # Kombiniere und bereichere Daten
        logger.info("🔄 Bereichere Gebäudedaten...")
        enriched_gdf = enrich_building_data(buildings_gdf, wfs_fetcher.fetch_data(bbox))
        enriched_path = project_dir['outputs'] / 'zone_enriched.geojson'
        enriched_gdf.to_file(enriched_path, driver='GeoJSON')
        
        # Erstelle CEA-Dateien
        logger.info("📄 Erstelle CEA-Dateien...")
        create_cea_files(enriched_gdf, project_dir, config)
        
        logger.info("✅ CEA-Workflow erfolgreich abgeschlossen")
        
    except Exception as e:
        logger.error(f"❌ Fehler im CEA-Workflow: {str(e)}")
        raise

def create_cea_files(zone_gdf: gpd.GeoDataFrame, output_dir: Path, config: dict):
    """Erstellt die CEA-kompatiblen Dateien aus den angereicherten Daten"""
    try:
        # Lade Mapping-Konfiguration
        mapping_config = config['cea']['mapping']
        
        # Erstelle zone.shp
        zone_mappings = mapping_config['zone_shp']['mappings']
        zone_gdf = zone_gdf.copy()
        
        # Mappe und transformiere Felder
        for target_col, mapping in zone_mappings.items():
            source_col = mapping['source']
            transform_type = mapping['transform']
            
            if source_col in zone_gdf.columns:
                if transform_type == 'int':
                    zone_gdf[target_col] = zone_gdf[source_col].astype(int)
                elif transform_type == 'float':
                    zone_gdf[target_col] = zone_gdf[source_col].astype(float)
                else:
                    zone_gdf[target_col] = zone_gdf[source_col].astype(str)
            else:
                zone_gdf[target_col] = None
        
        # Speichere zone.shp
        zone_path = output_dir / 'inputs' / 'building-geometry' / 'zone.shp'
        zone_gdf.to_file(zone_path)
        
        # Erstelle typology.dbf
        typology_mappings = mapping_config['typology_dbf']['mappings']
        typology_df = pd.DataFrame()
        
        # Mappe und transformiere Felder
        for target_col, mapping in typology_mappings.items():
            source_col = mapping['source']
            transform_type = mapping['transform']
            
            if source_col in zone_gdf.columns:
                if transform_type == 'int':
                    typology_df[target_col] = zone_gdf[source_col].astype(int)
                elif transform_type == 'float':
                    typology_df[target_col] = zone_gdf[source_col].astype(float)
                else:
                    typology_df[target_col] = zone_gdf[source_col].astype(str)
            else:
                typology_df[target_col] = None
        
        # Speichere typology.dbf
        typology_path = output_dir / 'inputs' / 'building-properties' / 'typology.dbf'
        typology_df.to_dbf(typology_path)
        
        logger.info(f"CEA-Dateien erstellt: {zone_path}, {typology_path}")
        
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der CEA-Dateien: {str(e)}")
        raise

def load_configs() -> dict:
    """Lädt alle Konfigurationsdateien"""
    try:
        configs = {
            'project': load_config(local_dir / "cfg" / "project_config.yml"),
            'wfs': load_config(local_dir / "cfg" / "wfs" / "wfs_config.yml")['vienna_wfs'],
            'osm': load_config(local_dir / "cfg" / "data_sources" / "osm_config.yml"),
            'cea': {
                'fields': load_config(local_dir / "cfg" / "cea" / "cea_fields.yml"),
                'mapping': load_config(local_dir / "cfg" / "cea" / "cea_mapping.yml")
            }
        }
        
        if not all(configs.values()):
            raise ValueError("❌ Fehler beim Laden der Konfigurationsdateien")
            
        # Stelle sicher, dass die WFS-Konfiguration korrekt ist
        if 'wfs' not in configs or not isinstance(configs['wfs'], dict):
            raise ValueError("❌ Ungültige WFS-Konfiguration")
            
        return configs
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfigurationen: {str(e)}")
        raise

def enrich_building_data(buildings_gdf: gpd.GeoDataFrame, wfs_data: dict) -> gpd.GeoDataFrame:
    """Reichert die Gebäudedaten mit WFS-Daten an"""
    try:
        enriched_gdf = buildings_gdf.copy()
        
        if not wfs_data:
            logger.warning("⚠️ Keine WFS-Daten zum Anreichern verfügbar")
            return enriched_gdf
        
        # Verarbeite jeden WFS Layer
        for layer_name, layer_data in wfs_data.items():
            if layer_data is None or layer_data.empty:
                logger.warning(f"⚠️ Keine Daten für Layer {layer_name}")
                continue
                
            logger.info(f"🔄 Reichere Daten mit {layer_name} an...")
            
            try:
                # Führe räumliche Verknüpfung durch
                joined = gpd.sjoin_nearest(
                    enriched_gdf,
                    layer_data,
                    how='left',
                    distance_col='distance'
                )
                
                # Füge neue Spalten hinzu (ohne Geometrie und Index)
                for col in layer_data.columns:
                    if col not in ['geometry', 'index', 'index_right'] and col not in enriched_gdf.columns:
                        enriched_gdf[f"{layer_name}_{col}"] = joined[col]
                        
                logger.info(f"✅ Layer {layer_name} erfolgreich verarbeitet")
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Anreichern mit Layer {layer_name}: {str(e)}")
                continue
        
        return enriched_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Anreichern der Gebäudedaten: {str(e)}")
        return buildings_gdf

if __name__ == "__main__":
    main() 
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
from utils.data_processing.cea_building_processor import CEABuildingProcessor

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
        
        # Initialisiere CEA Building Processor
        processor = CEABuildingProcessor(config['cea'], config['project'])
        
        # Verarbeite CityGML-Datei
        citygml_path = Path(config['paths']['inputs']['citygml']) / "099082.gml"
        if not processor.process_citygml(citygml_path):
            raise ValueError("❌ Fehler bei der CityGML-Verarbeitung")
            
        # Verarbeite CEA-Daten
        success, cea_data = processor.process_cea_data(scenario_path)
        if not success or cea_data is None:
            raise ValueError("❌ Fehler bei der CEA-Datenverarbeitung")
            
        # Speichere angereicherte Daten
        enriched_path = project_dir['outputs'] / 'zone_enriched.geojson'
        cea_data['zone'].to_file(enriched_path, driver='GeoJSON')
        logger.info(f"✅ Angereicherte Daten gespeichert: {enriched_path}")
        
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
        # Definiere Basis-Pfade
        local_dir = Path(__file__).resolve().parent
        cfg_dir = local_dir / "cfg"
        
        # Lade Konfigurationen
        configs = {}
        
        # Lade project_config.yml
        project_config_path = cfg_dir / "project_config.yml"
        if project_config_path.exists():
            with open(project_config_path, 'r', encoding='utf-8') as f:
                configs['project'] = yaml.safe_load(f)
                print("Lade Konfiguration: project_config.yml")
        
        # Lade CEA-spezifische Konfigurationen
        cea_configs = {
            'fields': "cea_fields.yml",
            'mapping': "cea_mapping.yml",
            'metrics': "building_metrics.yml"
        }
        
        configs['cea'] = {}
        for key, filename in cea_configs.items():
            file_path = cfg_dir / "cea" / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    configs['cea'][key] = yaml.safe_load(f)
                    print(f"Lade Konfiguration: {filename}")
        
        # Lade WFS-Konfiguration
        wfs_config_path = cfg_dir / "wfs" / "wfs_config.yml"
        if wfs_config_path.exists():
            with open(wfs_config_path, 'r', encoding='utf-8') as f:
                wfs_config = yaml.safe_load(f)
                configs['cea']['wfs'] = wfs_config.get('vienna_wfs', {})
                print("Lade Konfiguration: wfs_config.yml")
        
        # Setze Pfade
        configs['paths'] = {
            'inputs': {
                'citygml': local_dir / "data" / "inputs" / "citygml"
            },
            'outputs': {
                'buildings': local_dir / "data" / "outputs" / "buildings"
            }
        }
        
        if not all(configs.values()):
            raise ValueError("❌ Fehler beim Laden der Konfigurationsdateien")
            
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
import argparse
from pathlib import Path
import yaml
import sys
import os
from utils.data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from utils.data_sources.fetch_geojson_buildings import GeoJSONBuildingProcessor
from utils.CEA.process_citygml_buildings import process_citygml_buildings
from simpledbf import Dbf5
import geopandas as gpd
import pandas as pd

# Füge Projektverzeichnis zum Python-Path hinzu
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

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

def setup_project_structure(project_path, scenario_path):
    """Erstellt die Projektstruktur"""
    # absoluter Pfad zum Projekthauptverzeichnis
    script_path = os.path.abspath(__file__)  
    project_root = os.path.dirname(script_path) 
    config_path = os.path.join(project_root, 'cfg', 'cea_config.yml')
    
    # Debug-Ausgabe
    print(f"Script Pfad: {script_path}")
    print(f"Projekt Root: {project_root}")
    print(f"Suche Konfigurationsdatei unter: {config_path}")
    
    # Lade die globale Konfiguration
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Template-Konfigurationsdatei nicht gefunden unter: {config_path}")
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Erstelle Hauptverzeichnisse
    for path in [project_path, scenario_path]:
        path.mkdir(parents=True, exist_ok=True)
    
    # Erstelle Szenario-Unterverzeichnisse basierend auf der Konfiguration
    for folder in config['paths']['scenario_folders']['inputs'].values():
        (scenario_path / folder).mkdir(parents=True, exist_ok=True)
    
    # Kopiere oder erstelle cea_config.yml im Szenarioverzeichnis
    scenario_config = scenario_path / "cea_config.yml"
    
    if not scenario_config.exists():
        # Verwende den gleichen config_path wie oben
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as src:
                config = yaml.safe_load(src)
                
                # Aktualisiere den Szenariopfad für CEA
                config['cea_settings']['scenario_path'] = str(scenario_path)
                
                with scenario_config.open('w', encoding='utf-8') as dst:
                    yaml.dump(config, dst, allow_unicode=True)
        else:
            raise FileNotFoundError(f"Template-Konfigurationsdatei nicht gefunden unter: {config_path}")

def create_site_polygon(zone_path):
    """Erstellt ein Site-Polygon aus der Zone"""
    try:
        zone_gdf = gpd.read_file(zone_path)
        site_polygon = zone_gdf.unary_union.convex_hull
        return gpd.GeoDataFrame(geometry=[site_polygon], crs=zone_gdf.crs)
    except Exception as e:
        print(f"Fehler beim Erstellen des Site-Polygons: {str(e)}")
        raise

def check_required_files(geometry_path, properties_path):
    """Überprüft ob alle notwendigen Dateien existieren"""
    required_files = {
        'geometry': [
            geometry_path / 'zone.shp',
            geometry_path / 'site.shp'
        ],
        'properties': [
            properties_path / 'typology.dbf'
        ]
    }
    
    missing_files = []
    for category, files in required_files.items():
        for file_path in files:
            if not file_path.exists():
                missing_files.append(file_path)
    
    if missing_files:
        print("\nFehlende Dateien:")
        for file_path in missing_files:
            print(f"- {file_path}")
        return False
    
    return True

def main():
    try:
        # Projekt und Szenario Eingabe
        project = input("Bitte Projekt eingeben (default: ): ")
        scenario = input("Bitte Szenario eingeben (default: ): ") 
        print(f"\nVerarbeite Projekt: {project}, Szenario: {scenario}")

        # Lade Konfiguration
        config_path = project_root / "cfg" / "cea_config.yml"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Erstelle Projekt-Verzeichnisstruktur
        project_path = project_root / 'projects' / project / scenario
        input_path = project_path / 'inputs'
        
        # Erstelle alle benötigten Unterverzeichnisse
        geometry_path = input_path / 'building-geometry'
        properties_path = input_path / 'building-properties'
        networks_path = input_path / 'networks'
        technology_path = input_path / 'technology'
        
        for path in [geometry_path, properties_path, networks_path, technology_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        input_format = config['paths']['input'].get('format', 'citygml')
        input_file = project_root / config['paths']['input']['files'][input_format]
        
        print(f"\nInput Format: {input_format}")
        print(f"Input File: {input_file}")
        
        if not input_file.exists():
            raise FileNotFoundError(f"Eingabedatei nicht gefunden: {input_file}")
        
        if input_format == 'citygml':
            from utils.CEA.process_citygml_buildings import process_enriched_citygml, enrich_citygml_with_wfs
            
            print("\nPhase 1: Anreichern der CityGML mit WFS-Daten...")
            enriched_gml = enrich_citygml_with_wfs(input_file, config)
            print(f"✓ Enriched GML erstellt: {enriched_gml}")
            
            print("\nPhase 2: Erstelle CEA-Dateien aus enriched GML...")
            process_enriched_citygml(enriched_gml, geometry_path, properties_path, config)
            print("✓ CEA-Dateien erstellt")
            
        else:  # geojson
            from utils.data_sources.fetch_geojson_buildings import process_geojson_buildings
            result = process_geojson_buildings(
                geojson_path=input_file,
                geometry_path=geometry_path,
                properties_path=properties_path,
                config=config
            )
            
            processor = GeoJSONBuildingProcessor(config)
            processor.create_variant_scenarios(
                result['gdf'], 
                result['buildings_df'], 
                project_path
            )

        # Überprüfe ob alle notwendigen Dateien existieren
        if not check_required_files(geometry_path, properties_path):
            raise FileNotFoundError("Nicht alle erforderlichen Dateien wurden erstellt")
        
        print("\n✅ Gebäudedaten erfolgreich verarbeitet")
        print(f"\nErstellte Dateien in:")
        print(f"- Geometrien: {geometry_path}")
        print(f"- Eigenschaften: {properties_path}")
        print(f"- Netzwerke: {networks_path}")
        print(f"- Technologie: {technology_path}")
        
        # Verwende das zone.shp für das site polygon
        site_polygon = create_site_polygon(geometry_path / 'zone.shp')
        
        print("\n2. Erstelle Site Polygon...")
        site_polygon = create_site_polygon(geometry_path / 'zone.shp')
        save_site_polygon(site_polygon, geometry_path / 'site.shp')

        print("\n3. Hole OSM Gebäude...")
        from utils.data_sources.fetch_osm_buildings import (
            fetch_surrounding_buildings,
            process_osm_buildings,
            save_surrounding_buildings
        )
        
        # Stelle sicher, dass osm_defaults in der Konfiguration existiert
        if 'osm_defaults' not in config:
            print("Warnung: Keine OSM-Defaults in Konfiguration gefunden, verwende Standard-Werte")
            osm_defaults = {
                'building_height': 12,
                'floor_height': 3,
                'floors_ag': 4,
                'floors_bg': 1,
                'default_floors': 4,
                'building_type': "MFH",
                'building_use': "MULTI_RES",
                'construction_year': 1970,
                'protection_level': 0,
                'category': "MFH",
                'REFERENCE': "OSM",
                'building_type_mapping': {
                    'residential': ["MFH", "MULTI_RES"],
                    'apartments': ["MFH", "MULTI_RES"],
                    'house': ["SFH", "SINGLE_RES"],
                    'commercial': ["OFFICE", "OFFICE"],
                    'retail': ["RETAIL", "RETAIL"]
                }
            }
        else:
            osm_defaults = config['osm_defaults']
            
        print(f"Verwende OSM-Defaults: {osm_defaults}")
        
        osm_buildings = fetch_surrounding_buildings(site_polygon)
        processed_buildings = process_osm_buildings(osm_buildings, osm_defaults)
        save_surrounding_buildings(processed_buildings, geometry_path / 'surroundings.shp')

        print("\n4. Hole OSM Straßen...")
        from utils.data_sources.fetch_osm_streets import (
            fetch_streets_within_site,
            process_streets,
            save_streets
        )
        streets = fetch_streets_within_site(site_polygon, config)
        processed_streets = process_streets(streets)
        save_streets(processed_streets, networks_path / 'streets.shp')

        print("\n5. Starte CEA Workflow...")
        from utils.CEA.run_cea_workflow import run_cea_workflow
        run_cea_workflow(project_path)

        print("\nVerarbeitung abgeschlossen!")
        print(f"Daten wurden in {project_path} gespeichert.")
        print("CEA Workflow wurde erfolgreich ausgeführt.")

    except Exception as e:
        print(f"Fehler: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
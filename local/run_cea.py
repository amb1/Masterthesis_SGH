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

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent
sys.path.append(str(local_dir))

from utils.data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings
from utils.CEA.run_cea_workflow import run_cea_workflow
from utils.data_sources.fetch_wfs_data import ViennaWFS
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
    
    return config

def create_site_polygon(zone_path):
    """Erstellt ein Site-Polygon aus der Zone"""
    try:
        zone_gdf = gpd.read_file(zone_path)
        site_polygon = zone_gdf.unary_union.convex_hull
        site_gdf = gpd.GeoDataFrame(geometry=[site_polygon])
        site_path = os.path.join(zone_path.parent, "site.shp")
        site_gdf.to_file(site_path)
        return site_path
    except Exception as e:
        print(f"Fehler beim Erstellen des Site-Polygons: {str(e)}")
        raise

def check_required_files(geometry_path, properties_path):
    """Überprüft ob alle notwendigen Dateien existieren"""
    required_files = {
        'geometry': [
            geometry_path / 'zone.shp',
            geometry_path / 'site.shp',
            geometry_path / 'surroundings.shp'
        ],
        'properties': [
            properties_path / 'typology.shp'
        ],
        'networks': [
            geometry_path.parent / 'networks' / 'streets.shp'
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

def convert_csv_to_shp(csv_path: Path, shp_path: Path, config: dict) -> None:
    """Konvertiert eine CSV-Datei in ein Shapefile mit den definierten Feldern."""
    try:
        # Lade die CSV-Datei
        df = pd.read_csv(csv_path)
        
        # Erstelle leere Geometrien für jedes Gebäude
        empty_geometry = [Point(0, 0) for _ in range(len(df))]
        
        # Erstelle GeoDataFrame mit den definierten Feldern
        gdf = gpd.GeoDataFrame(
            df,
            geometry=empty_geometry,
            crs="EPSG:4326"
        )
        
        # Stelle sicher, dass das Zielverzeichnis existiert
        shp_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Speichere als Shapefile mit den definierten Feldern
        gdf.to_file(shp_path, driver='ESRI Shapefile')
        
        # Kurze Verzögerung, um sicherzustellen, dass die Datei geschrieben wurde
        time.sleep(0.1)
        
        # Überprüfe, ob die Datei existiert
        if not shp_path.exists():
            raise FileNotFoundError(f"Shapefile konnte nicht erstellt werden: {shp_path}")
            
    except Exception as e:
        raise Exception(f"Fehler beim Konvertieren der CSV-Datei in Shapefile: {str(e)}")

def load_config(config_path: Path) -> dict:
    """Lädt die Konfigurationsdateien."""
    try:
        print(f"Lade Konfiguration: {config_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
            
        with open(config_path, encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        if config is None:
            raise ValueError(f"Konfigurationsdatei ist leer: {config_path}")
            
        return config
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
        return None

def process_citygml(config, geometry_path, properties_path):
    """Verarbeitet CityGML Datei"""
    try:
        # Definiere project_root
        project_root = Path(__file__).resolve().parent

        # Lade CityGML Konfiguration
        citygml_config = load_config(project_root / "cfg" / "data_sources" / "vienna_citygml_normalized.yml")
        if not citygml_config:
            raise Exception("Fehler beim Laden der CityGML Konfiguration")

        # Lade CEA Konfiguration
        cea_config = load_config(project_root / "cfg" / "cea" / "cea_fields.yml")
        if not cea_config:
            raise Exception("Fehler beim Laden der CEA Konfiguration")

        # Lade Projekt Konfiguration
        project_config = load_config(project_root / "cfg" / "project_config.yml")
        if not project_config:
            raise Exception("Fehler beim Laden der Projekt Konfiguration")

        # Verarbeite CityGML
        input_file = project_root / project_config['paths']['inputs']['citygml'] / "099082.gml"
        if not input_file.exists():
            raise FileNotFoundError(f"CityGML Datei nicht gefunden: {input_file}")

        print(f"Verarbeite CityGML: {input_file}")
        buildings_gdf = fetch_citygml_buildings(
            citygml_path=input_file,
            config=citygml_config,
            cea_config=cea_config
        )

        if buildings_gdf is None:
            raise Exception("Keine Gebäude in der CityGML-Datei gefunden")

        # Speichere Ergebnisse
        buildings_gdf.to_file(geometry_path / "zone.shp", driver="ESRI Shapefile")
        print(f"✅ Geometrien gespeichert in: {geometry_path / 'zone.shp'}")

        # Erstelle Properties DataFrame
        properties_df = buildings_gdf.drop(columns=['geometry'])
        properties_df.to_csv(properties_path / "typology.csv", index=False)
        print(f"✅ Eigenschaften gespeichert in: {properties_path / 'typology.csv'}")

        return buildings_gdf

    except Exception as e:
        raise Exception(f"Fehler bei der Verarbeitung der CityGML-Datei: {str(e)}")

def main():
    """Hauptfunktion zum Ausführen des CEA-Workflows."""
    try:
        # Hole Projektinformationen
        project_name, scenario_name, project_path, scenario_path = get_project_info()
        
        # Erstelle Projektstruktur
        config = setup_project_structure(project_path, scenario_path)
        
        # Definiere Pfade
        properties_path = scenario_path / "inputs" / "building-properties"
        geometry_path = scenario_path / "inputs" / "building-geometry"
        
        # Lade Konfiguration
        config = load_config(local_dir / "cfg" / "data_sources" / "vienna_citygml_normalized.yml")
        
        # Initialisiere CEA Building Processor
        cea_processor = CEABuildingProcessor(config)
        
        # Verarbeite Gebäude
        buildings = process_citygml(config, geometry_path, properties_path)
        
        # Verarbeite Gebäude für CEA
        processed_buildings = []
        for building in buildings:
            processed = cea_processor.process_building(building)
            processed_buildings.append(processed)
            
        # Erstelle DataFrames für die Shapefiles
        zone_df = pd.DataFrame(processed_buildings)
        typology_df = pd.DataFrame(processed_buildings)
        
        # Speichere als CSV
        zone_csv = properties_path / 'zone.csv'
        typology_csv = properties_path / 'typology.csv'
        zone_df.to_csv(zone_csv, index=False)
        typology_df.to_csv(typology_csv, index=False)
        
        # Konvertiere zu Shapefiles
        zone_shp = properties_path / 'zone.shp'
        typology_shp = properties_path / 'typology.shp'
        convert_csv_to_shp(zone_csv, zone_shp, config)
        convert_csv_to_shp(typology_csv, typology_shp, config)
        
        print("✓ CEA-Dateien erstellt")

    except Exception as e:
        print(f"❌ Fehler beim Ausführen des CEA-Workflows: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
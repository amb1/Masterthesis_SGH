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
from typing import Optional, Dict
from pyproj import Transformer
import numpy as np
import random

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent
sys.path.append(str(local_dir))

from utils.data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings, CityGMLBuildingProcessor as CityGMLFetcher
from utils.data_sources.fetch_osm_buildings import (
    fetch_surrounding_buildings,
    process_osm_buildings,
    save_surrounding_buildings,
    fetch_osm_buildings
)
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_sources.fetch_wfs_data import ViennaWFS
from utils.config_loader import load_config
from utils.data_processing.cea_building_processor import CEABuildingProcessor
from utils.setup_project_paths import setup_project_paths
from utils.transformations import transform_value

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
        print("\nCEA Projekt-Setup")
        print("=" * 50)
        project_name = input("Bitte Projektnamen eingeben: ").strip()
        
        # Zeige existierende Szenarien für das Projekt
        project_path = Path("projects") / project_name
        if project_path.exists():
            existing_scenarios = [d.name for d in project_path.iterdir() if d.is_dir()]
            if existing_scenarios:
                print(f"\nExistierende Szenarien für {project_name}:")
                for scenario in existing_scenarios:
                    print(f"- {scenario}")
                print("\n")
        
        scenario_name = input("Bitte Szenarionamen eingeben: ").strip()
    
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
            print(f"\n⚠️ Szenario '{scenario_name}' existiert bereits.")
            choice = input("Möchten Sie das bestehende Szenario überschreiben? (y/n): ").lower()
        
        if choice != 'y':
            print("Abbruch.")
            sys.exit(0)
    
    return project_name, scenario_name, project_path, scenario_path

def create_backup(scenario_path: Path) -> Optional[Path]:
    """Erstellt ein Backup des Szenarios
    
    Args:
        scenario_path (Path): Pfad zum Szenarioverzeichnis
        
    Returns:
        Optional[Path]: Pfad zum Backup-Verzeichnis oder None
    """
    try:
        # Erstelle Backup-Verzeichnis
        backup_dir = scenario_path.parent / f"{scenario_path.name}_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Kopiere Dateien
        for file_path in scenario_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(scenario_path)
                backup_path = backup_dir / relative_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                backup_path.write_bytes(file_path.read_bytes())
                
        logger.info(f"✅ Backup erstellt: {backup_dir}")
        return backup_dir
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Backups: {str(e)}")
        return None

def cleanup_project(project_path: Path) -> bool:
    """Bereinigt das Projektverzeichnis
    
    Args:
        project_path (Path): Pfad zum Projektverzeichnis
        
    Returns:
        bool: True wenn erfolgreich, False sonst
    """
    try:
        # Lösche temporäre Dateien
        temp_files = list(project_path.rglob('*.tmp'))
        for temp_file in temp_files:
            temp_file.unlink()
            
        # Lösche leere Verzeichnisse
        for dir_path in project_path.rglob('*'):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                
        logger.info("✅ Projektverzeichnis bereinigt")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Projektbereinigung: {str(e)}")
        return False

def validate_project_structure(project_path: Path, scenario_path: Path) -> bool:
    """Überprüft die CEA-Projektstruktur
    
    Args:
        project_path (Path): Pfad zum Projektverzeichnis
        scenario_path (Path): Pfad zum Szenarioverzeichnis
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    try:
        # Überprüfe Projektverzeichnis
        if not project_path.exists():
            logger.error(f"❌ Projektverzeichnis nicht gefunden: {project_path}")
            return False
            
        # Überprüfe Szenarioverzeichnis
        if not scenario_path.exists():
            logger.error(f"❌ Szenarioverzeichnis nicht gefunden: {scenario_path}")
            return False
            
        # Überprüfe erforderliche Verzeichnisse
        required_dirs = [
            'inputs/building-geometry',
            'inputs/building-properties',
            'inputs/networks',
            'outputs/data'
        ]
        
        for dir_path in required_dirs:
            full_path = scenario_path / dir_path
            if not full_path.exists():
                logger.error(f"❌ Erforderliches Verzeichnis nicht gefunden: {full_path}")
                return False
                
        # Überprüfe erforderliche Dateien
        required_files = [
            'inputs/building-geometry/zone.shp',
            'inputs/building-geometry/site.shp',
            'inputs/building-geometry/surroundings.shp',
            'inputs/building-properties/typology.dbf',
            'inputs/networks/streets.shp'
        ]
        
        for file_path in required_files:
            full_path = scenario_path / file_path
            if not full_path.exists():
                logger.error(f"❌ Erforderliche Datei nicht gefunden: {full_path}")
                return False
                
        logger.info("✅ Projektstruktur erfolgreich validiert")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Validierung der Projektstruktur: {str(e)}")
        return False

def setup_project_structure(project_path: Path, scenario_path: Path) -> Dict[str, Path]:
    """Erstellt die CEA-Projektstruktur
    
    Args:
        project_path (Path): Pfad zum Projektverzeichnis
        scenario_path (Path): Pfad zum Szenarioverzeichnis
        
    Returns:
        Dict[str, Path]: Dictionary mit den Pfaden der erstellten Verzeichnisse
    """
    try:
        # Erstelle Backup wenn nötig
        if scenario_path.exists():
            backup_path = create_backup(scenario_path)
            if backup_path:
                logger.info(f"✅ Backup erstellt in: {backup_path}")
        
        # Definiere Verzeichnisstruktur
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
        created_dirs = {}
        for parent, children in dirs.items():
            parent_path = scenario_path / parent
            parent_path.mkdir(parents=True, exist_ok=True)
            created_dirs[parent] = parent_path
            
            for child, files in children.items():
                child_path = parent_path / child
                child_path.mkdir(parents=True, exist_ok=True)
                created_dirs[f"{parent}_{child}"] = child_path
                
                # Erstelle leere Dateien
                for file in files:
                    file_path = child_path / file
                    if not file_path.exists():
                        file_path.touch()
        
        # Validiere Projektstruktur
        if not validate_project_structure(project_path, scenario_path):
            raise ValueError("❌ Projektstruktur konnte nicht validiert werden")
        
        # Bereinige Projektverzeichnis
        if not cleanup_project(project_path):
            logger.warning("⚠️ Projektbereinigung nicht vollständig")
        
        logger.info("✅ Projektstruktur erfolgreich erstellt und validiert")
        return created_dirs
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der Projektstruktur: {str(e)}")
        raise

def ensure_directories(config: dict):
    """Stellt sicher, dass alle benötigten Verzeichnisse existieren"""
    try:
        # Erstelle Basis-Verzeichnisse
        paths = config['project']['paths']
        
        # Erstelle Verzeichnisse
        for parent, children in dirs.items():
            parent_path = scenario_path / parent
            parent_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Verzeichnis erstellt: {parent_path}")
            
            for child, files in children.items():
                child_path = parent_path / child
                child_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"✅ Verzeichnis erstellt: {child_path}")
                
                # Erstelle leere Dateien wenn angegeben
                for file in files:
                    file_path = child_path / file
                    if not file_path.exists():
                        file_path.touch()
        
        # Erstelle temporäres Verzeichnis
        temp_dir = scenario_path / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Temporäres Verzeichnis erstellt: {temp_dir}")
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der CEA-Verzeichnisse: {str(e)}")
        raise

def main():
    """Hauptfunktion für den CEA-Workflow"""
    try:
        # Lade Konfigurationen
        config = load_configs()
        
        # Erstelle CEA-Projektstruktur
        project_name, scenario_name, project_path, scenario_path = get_project_info()
        created_dirs = setup_project_structure(project_path, scenario_path)
        
        # Lade CityGML-Daten
        logger.info("🔄 Lade CityGML-Daten...")
        citygml_config = config['project']['data_source']['citygml']
        # Verwende absoluten Pfad für CityGML-Datei
        local_dir = Path(__file__).resolve().parent
        citygml_path = local_dir.parent / citygml_config['base_path'] / citygml_config['default_file']
        logger.info(f"📂 Lade CityGML-Datei von: {citygml_path}")
        
        # Erstelle CityGML Processor mit korrekter Konfiguration
        processor = CityGMLFetcher(citygml_config)
        buildings_gdf = processor.extract_buildings(str(citygml_path))
        
        if buildings_gdf is None:
            raise ValueError("Fehler beim Laden der CityGML-Daten")
        logger.info(f"✅ {len(buildings_gdf)} Gebäude aus CityGML geladen")
        
        # Entferne problematische Felder direkt nach dem Laden
        fields_to_remove = ['Gebäudemo', 'Gebäudein']
        for field in fields_to_remove:
            if field in buildings_gdf.columns:
                buildings_gdf = buildings_gdf.drop(columns=[field])
                logger.info(f"✅ Feld {field} entfernt")
        
        # Passe Feldbreiten an
        buildings_gdf = adjust_field_widths(buildings_gdf)
        
        # Erstelle Site-Polygon
        logger.info("🔄 Erstelle Site-Polygon...")
        site_gdf = create_site_polygon(buildings_gdf)
        
        # Speichere Site-Polygon
        site_shp_path = created_dirs['inputs_building-geometry'] / 'site.shp'
        site_gdf.to_file(site_shp_path)
        logger.info(f"✅ Site-Polygon gespeichert: {site_shp_path}")
        
        # Hole WFS-Daten
        logger.info("🔄 Hole WFS-Daten...")
        wfs_config = config.get('wfs', {})
        if not wfs_config:
            logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            wfs_config = {}
        
        wfs_processor = ViennaWFS(wfs_config)
        
        # Transformiere Koordinaten von EPSG:31256 nach EPSG:4326 für WFS-Anfragen
        logger.info("🔄 Transformiere Koordinaten von EPSG:31256 nach EPSG:4326")
        site_gdf_wgs84 = site_gdf.to_crs('EPSG:4326')
        
        # Berechne BBOX mit Buffer
        buffer_meters = 50  # 50 Meter Buffer
        site_gdf_mercator = site_gdf.to_crs('EPSG:3857')  # Für metrische Berechnungen
        search_area = site_gdf_mercator.geometry.buffer(buffer_meters).unary_union
        bbox = search_area.bounds  # (minx, miny, maxx, maxy)
        
        # Transformiere BBOX zurück nach WGS84
        transformer = Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True)
        min_lon, min_lat = transformer.transform(bbox[0], bbox[1])
        max_lon, max_lat = transformer.transform(bbox[2], bbox[3])
        
        # Formatiere BBOX für WFS (minx,miny,maxx,maxy)
        bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat},EPSG:4326"
        logger.info(f"🔄 Verwende BBOX für WFS-Anfrage: {bbox_str}")
        
        # Verarbeite WFS-Streams
        logger.info("🔄 Verarbeite Streams...")
        wfs_data = {}
        
        for stream in wfs_config['streams']:
            try:
                stream_name = stream['name']
                layer_name = stream['layer']
                logger.info(f"🔄 Verarbeite Layer: {layer_name}")
                logger.info(f"🔄 Hole Daten für Layer: {layer_name}")
                
                # Hole Daten
                gdf = wfs_processor.fetch_layer(layer_name, bbox=bbox_str)
                
                if gdf is not None and not gdf.empty:
                    wfs_data[stream_name] = gdf
                    logger.info(f"✅ {len(gdf)} Features für {stream_name} gefunden")
                else:
                    logger.warning(f"⚠️ Keine Daten für Layer {layer_name} gefunden")
                    
            except Exception as e:
                logger.error(f"❌ Fehler beim Abrufen von {stream_name}: {str(e)}")
                continue
        
        # Anreichere Gebäudedaten mit WFS-Informationen
        if wfs_data:
            enriched_buildings = enrich_building_data(buildings_gdf, wfs_data)
        else:
            logger.warning("⚠️ Keine WFS-Daten zum Anreichern verfügbar")
            enriched_buildings = buildings_gdf
        
        # Speichere angereicherte Gebäudedaten
        enriched_geojson_path = created_dirs['inputs_building-geometry'] / 'buildings_enriched.geojson'
        enriched_buildings.to_file(enriched_geojson_path, driver='GeoJSON')
        logger.info(f"✅ Angereicherte Gebäudedaten gespeichert: {enriched_geojson_path}")
        
        # Erstelle CEA-Dateien
        logger.info("🔄 Erstelle CEA-Dateien...")
        create_cea_files(enriched_buildings, scenario_path / 'inputs', config)
        
        # Hole Umgebungsgebäude
        logger.info("🔄 Hole Umgebungsgebäude...")
        if 'osm' in config:
            osm_config = config['osm']
            surroundings_gdf = fetch_surrounding_buildings(site_gdf, osm_config)
        else:
            logger.warning("⚠️ Keine OSM-Konfiguration gefunden, verwende Standardwerte")
            surroundings_gdf = fetch_surrounding_buildings(site_gdf, {'buildings': {'buffer_distance': 100}})

        if not surroundings_gdf.empty:
            logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gefunden")
            # Verarbeite und speichere Umgebungsgebäude
            processed_surroundings = process_osm_buildings(surroundings_gdf, osm_config.get('osm', {}).get('buildings', {}).get('defaults', {}))
            save_surrounding_buildings(processed_surroundings, created_dirs['inputs_building-geometry'] / 'surroundings.shp')
        else:
            logger.warning("⚠️ Keine Umgebungsgebäude gefunden")
        
        # Hole Straßen
        logger.info("🔄 Hole Straßen...")
        streets_gdf = fetch_osm_streets(site_gdf, config)
        if not streets_gdf.empty:
            streets_path = created_dirs['inputs_networks'] / 'streets.shp'
            streets_gdf.to_file(streets_path)
            logger.info(f"✅ {len(streets_gdf)} Straßen gespeichert: {streets_path}")
        
        logger.info("✅ CEA-Workflow erfolgreich abgeschlossen")
        
    except Exception as e:
        logger.error(f"❌ Fehler im CEA-Workflow: {str(e)}")
        raise

def adjust_field_widths(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Passt die Feldbreiten für Shapefiles an, um Schreibfehler zu vermeiden."""
    try:
        adjusted_gdf = gdf.copy()

        # Entferne problematische Felder direkt
        fields_to_remove = ['Gebäudemo', 'Gebäudein']
        for field in fields_to_remove:
            if field in adjusted_gdf.columns:
                adjusted_gdf = adjusted_gdf.drop(columns=[field])
                logger.info(f"✅ Feld {field} entfernt")

        return adjusted_gdf

    except Exception as e:
        logger.error(f"❌ Fehler beim Anpassen der Feldbreiten: {str(e)}")
        return gdf

def get_year_and_suffix(period_str, wfs_config):
    """
    Bestimmt das Jahr und den Suffix basierend auf der Bauperiode.
    
    Args:
        period_str: String der Bauperiode (z.B. "1848 -1918")
        wfs_config: WFS Konfigurationsdaten
        
    Returns:
        tuple: (year, suffix)
    """
    if pd.isna(period_str):
        logging.warning(f"Keine Bauperiode gefunden, verwende Standardwerte")
        return 2000, "_I"
        
    # Zuerst prüfen wir das period_ranges Mapping
    period_ranges = wfs_config.get('period_ranges', {})
    if period_str in period_ranges:
        start_year, end_year = period_ranges[period_str]
        year = random.randint(start_year, end_year)
        logging.info(f"Zufälliges Jahr {year} generiert für Periode {period_str}")
    else:
        # Wenn keine Zuordnung gefunden wurde, verwenden wir Standardwerte
        logging.warning(f"Keine Zuordnung für Periode {period_str} gefunden, verwende Jahr 2000")
        year = 2000

    # Suffix basierend auf dem Jahr bestimmen
    building_periods = wfs_config.get('building_periods', [])
    for period in building_periods:
        start = period['start'] if period['start'] is not None else float('-inf')
        end = period['end'] if period['end'] is not None else float('inf')
        if start <= year <= end:
            suffix = period['suffix']
            logging.info(f"Suffix {suffix} zugewiesen für Jahr {year}")
            return year, suffix
            
    # Fallback wenn kein passendes Intervall gefunden wurde
    logging.warning(f"Kein passendes Intervall für Jahr {year} gefunden, verwende _I")
    return year, "_I"

def create_cea_files(buildings_gdf: gpd.GeoDataFrame, output_dir: Path, config: dict):
    """Erstellt die CEA-Eingabedateien."""
    try:
        # Erstelle eine bereinigte Kopie des DataFrames
        clean_buildings_gdf = buildings_gdf.copy()
        
        # Erstelle zone.shp
        zone_gdf = gpd.GeoDataFrame(geometry=clean_buildings_gdf.geometry, crs=clean_buildings_gdf.crs)
        
        # Hole die Mappings aus der Konfiguration
        cea_mapping = config.get('cea', {}).get('mapping', {})
        zone_mappings = cea_mapping.get('zone_mappings', {})
        
        # Erstelle den Namen aus Straße und Hausnummer
        if 'Adresse_STR' in clean_buildings_gdf.columns and 'Adresse_ONR' in clean_buildings_gdf.columns:
            zone_gdf['Name'] = clean_buildings_gdf.apply(
                lambda row: f"{row['Adresse_STR']}_{str(row['Adresse_ONR']).replace(',', '')}" if pd.notna(row['Adresse_STR']) and pd.notna(row['Adresse_ONR']) else f"Building_{row.name}",
                axis=1
            )
        else:
            zone_gdf['Name'] = [f"Building_{i}" for i in range(len(clean_buildings_gdf))]
            
        # Kopiere die Namen auch in die REFERENCE-Spalte
        zone_gdf['REFERENCE'] = zone_gdf['Name']
        
        # Wende die Mappings für Zone an
        for field, mapping in zone_mappings.items():
            try:
                value = None
                # Versuche die Werte aus den Quellen zu holen
                if 'sources' in mapping:
                    for source, source_field in mapping['sources'].items():
                        if source_field in clean_buildings_gdf.columns:
                            value = clean_buildings_gdf[source_field]
                            logger.info(f"✅ {field}: Verwende Werte aus {source_field}")
                            break
                
                # Verwende Default-Wert wenn keine Quelle gefunden wurde
                if value is None and 'default' in mapping:
                    value = mapping['default']
                    if isinstance(value, (int, float, str)):
                        value = pd.Series([value] * len(clean_buildings_gdf))
                    logger.info(f"ℹ️ {field}: Verwende Default-Wert {value}")
                
                # Wende Transformation an
                if value is not None and 'transform' in mapping:
                    transform_name = mapping['transform']
                    if transform_name == 'to_int':
                        zone_gdf[field] = pd.to_numeric(value, errors='coerce').fillna(mapping.get('default', 0)).astype('Int64')
                    elif transform_name == 'to_float':
                        zone_gdf[field] = pd.to_numeric(value, errors='coerce').fillna(mapping.get('default', 0.0))
                    elif transform_name == 'none':
                        zone_gdf[field] = value
                    logger.info(f"✅ {field}: Transformation {transform_name} angewendet")
                else:
                    zone_gdf[field] = value
                    
            except Exception as e:
                logger.warning(f"⚠️ Fehler beim Mapping von {field}: {str(e)}")
                if mapping.get('required', False):
                    raise
        
        # Erstelle typology.shp
        typology_gdf = gpd.GeoDataFrame(geometry=clean_buildings_gdf.geometry, crs=clean_buildings_gdf.crs)
        
        # Kopiere Name und REFERENCE aus zone_gdf
        typology_gdf['Name'] = zone_gdf['Name']
        typology_gdf['REFERENCE'] = zone_gdf['REFERENCE']
        logger.info("✅ Name und REFERENCE aus zone_gdf kopiert")
        
        # Hole die Mappings für die Typologie
        wfs_config = config.get('wfs', {})
        if not wfs_config:
            logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            wfs_config = {}
        
        building_types = wfs_config.get('building_types', {})
        standard_prefix_mapping = building_types.get('standard_prefix', {})
        use_type_mapping = building_types.get('use_type', {})
        
        # Logge die verfügbaren Spalten
        logger.info("📋 Verfügbare Spalten für Gebäudetyp und Bauperiode:")
        for col in clean_buildings_gdf.columns:
            if 'BAUTYP' in col or 'BAUP' in col:
                logger.info(f"  - {col}")
        
        # Verarbeite jeden Eintrag
        for idx, row in clean_buildings_gdf.iterrows():
            try:
                # Bestimme den Gebäudetyp
                building_type = None
                for field in ['Gebäudeinfo_L_BAUTYP', 'Gebäudetypologie_OBJ_STR', 'L_BAUTYP', 'BAUTYP_TXT']:
                    if field in row and pd.notna(row[field]):
                        building_type = row[field]
                        logger.info(f"Gebäudetyp gefunden in {field}: {building_type}")
                        break
                
                if building_type is None:
                    building_type = 'UNKNOWN'
                    logger.warning(f"Kein Gebäudetyp für Gebäude {idx} gefunden")
                
                # Hole den Prefix und USE_TYPE aus dem Mapping
                prefix = standard_prefix_mapping.get(building_type, 'MFH')
                use_type = use_type_mapping.get(building_type, 'RESIDENTIAL')
                
                # Bestimme die Bauperiode
                period = None
                for field in ['Gebäudeinfo_L_BAUP', 'L_BAUP', 'BAUP_TXT']:
                    if field in row and pd.notna(row[field]):
                        period = row[field]
                        logger.info(f"Bauperiode gefunden in {field}: {period}")
                        break
                
                # Bestimme das Baujahr und den Suffix
                year, suffix = get_year_and_suffix(period, wfs_config)
                
                # Setze die Werte
                typology_gdf.at[idx, 'YEAR'] = year
                typology_gdf.at[idx, 'STANDARD'] = f"{prefix}{suffix}"
                
                # Setze die Nutzungstypen basierend auf dem USE_TYPE Mapping
                typology_gdf.at[idx, '1ST_USE'] = use_type
                typology_gdf.at[idx, '1ST_USE_R'] = 1.0
                typology_gdf.at[idx, '2ND_USE'] = 'NONE'
                typology_gdf.at[idx, '2ND_USE_R'] = 0.0
                typology_gdf.at[idx, '3RD_USE'] = 'NONE'
                typology_gdf.at[idx, '3RD_USE_R'] = 0.0
                
                logger.info(f"✅ Gebäude {idx} verarbeitet: {prefix}{suffix}, {use_type}, Jahr {year}")
                
            except Exception as e:
                logger.warning(f"⚠️ Fehler bei der Verarbeitung von Gebäude {idx}: {str(e)}")
                continue
        
        # Speichere die Dateien
        zone_output = output_dir / 'building-geometry' / 'zone.shp'
        typology_output = output_dir / 'building-properties' / 'typology.shp'
        
        zone_output.parent.mkdir(parents=True, exist_ok=True)
        typology_output.parent.mkdir(parents=True, exist_ok=True)
        
        zone_gdf.to_file(zone_output)
        typology_gdf.to_file(typology_output)
        
        logger.info(f"Created {len(zone_gdf)} records")
        logger.info(f"Created {len(typology_gdf)} records")
        logger.info("✅ CEA-Dateien erstellt:")
        logger.info(f"  - Zone: {zone_output}")
        logger.info(f"  - Typologie: {typology_output}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der CEA-Dateien: {str(e)}")
        return False

def load_configs() -> dict:
    """Lädt alle Konfigurationsdateien"""
    try:
        # Definiere Basis-Pfade
        local_dir = Path(__file__).resolve().parent
        cfg_dir = local_dir / "cfg"
        
        configs = {}
        
        # Lade project_config.yml
        project_config_path = cfg_dir / "project_config.yml"
        configs['project'] = load_config(project_config_path)
        logger.info("✅ project_config.yml geladen")
        
        # Konvertiere relative Pfade zu absoluten Pfaden
        if 'paths' in configs['project']:
            for category in ['inputs', 'outputs']:
                if category in configs['project']['paths']:
                    for key, path in configs['project']['paths'][category].items():
                        configs['project']['paths'][category][key] = str(local_dir / path)
        
        # Lade CEA-spezifische Konfigurationen
        cea_configs = {
            'fields': "cea_fields.yml",
            'mapping': "cea_mapping.yml",
            'metrics': "building_metrics.yml"
        }
        
        configs['cea'] = {}
        for key, filename in cea_configs.items():
            file_path = cfg_dir / "cea" / filename
            configs['cea'][key] = load_config(file_path)
            if configs['cea'][key] is None:
                raise ValueError(f"❌ Konnte {filename} nicht laden")
            logger.info(f"✅ {filename} geladen")
        
        # Lade WFS-Konfiguration
        wfs_config_path = cfg_dir / "wfs" / "wfs_config.yml"
        wfs_config = load_config(wfs_config_path)
        if wfs_config and 'vienna_wfs' in wfs_config:
            configs['wfs'] = wfs_config['vienna_wfs']
            logger.info("✅ WFS-Konfiguration geladen")
            
            # Validiere wichtige WFS-Konfigurationsabschnitte
            if 'building_types' not in configs['wfs']:
                logger.warning("⚠️ Keine building_types in WFS-Konfiguration gefunden")
            if 'period_ranges' not in configs['wfs']:
                logger.warning("⚠️ Keine period_ranges in WFS-Konfiguration gefunden")
            if 'building_periods' not in configs['wfs']:
                logger.warning("⚠️ Keine building_periods in WFS-Konfiguration gefunden")
        else:
            logger.error("❌ WFS-Konfiguration konnte nicht geladen werden")
            configs['wfs'] = {}
            
        # Lade OSM-Konfiguration
        osm_config_path = cfg_dir / "osm" / "osm_config.yml"
        configs['osm'] = load_config(osm_config_path)
        if configs['osm']:
            logger.info("✅ osm_config.yml geladen")
        else:
            raise ValueError("❌ OSM-Konfiguration konnte nicht geladen werden")
        
        # Validiere CEA-Mapping
        if 'mapping' not in configs['cea'] or not configs['cea']['mapping']:
            raise ValueError("❌ CEA-Mapping-Konfiguration fehlt oder ist leer")
            
        if 'zone_mappings' not in configs['cea']['mapping'] or 'typology_mappings' not in configs['cea']['mapping']:
            raise ValueError("❌ CEA-Mapping-Konfiguration fehlt erforderliche Mappings")
        
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
                    max_distance=1.0,  # Maximale Distanz von 1 Meter
                    distance_col='distance'
                )
                
                # Protokolliere die Anzahl der erfolgreichen Verknüpfungen
                matched = joined[~joined['index_right'].isna()]
                logger.info(f"✅ {len(matched)} von {len(enriched_gdf)} Gebäuden mit {layer_name} verknüpft")
                
                # Füge neue Spalten hinzu und behalte die Originalnamen bei
                for col in layer_data.columns:
                    if col not in ['geometry', 'index', 'index_right']:
                        # Behalte den Originalnamen bei
                        enriched_gdf[f"{layer_name}_{col}"] = joined.groupby(level=0)[col].first()
                        
                logger.info(f"✅ Layer {layer_name} erfolgreich verarbeitet")
                
            except Exception as e:
                logger.error(f"❌ Fehler beim Anreichern mit Layer {layer_name}: {str(e)}")
                continue
        
        # Logge die verfügbaren Spalten für das Mapping
        logger.info("📋 Verfügbare Spalten für CEA-Mapping:")
        for col in enriched_gdf.columns:
            if col != 'geometry':
                logger.info(f"  - {col}")
        
        return enriched_gdf
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Anreichern der Gebäudedaten: {str(e)}")
        return buildings_gdf

if __name__ == "__main__":
    main() 
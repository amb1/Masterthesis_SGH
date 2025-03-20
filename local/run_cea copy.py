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
        wfs_config = config['wfs']
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
        buffer_meters = 100  # 100 Meter Buffer für Umgebungsgebäude

        # Erstelle OSM-Konfiguration
        osm_config = {
            'buildings': {
                'buffer_distance': buffer_meters,
                'defaults': {
                    'height': 10,
                    'floors': 3,
                    'year': 1990
                }
            }
        }

        # Hole Umgebungsgebäude von OSM
        surroundings_gdf = fetch_surrounding_buildings(site_gdf, osm_config)
        if not surroundings_gdf.empty:
            surroundings_path = created_dirs['inputs_building-geometry'] / 'surroundings.shp'
            surroundings_gdf.to_file(surroundings_path)
            logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gespeichert: {surroundings_path}")
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

def create_cea_files(zone_gdf: gpd.GeoDataFrame, output_dir: Path, config: dict):
    """Erstellt die CEA-Dateien aus den Gebäudedaten"""
    try:
        # Validiere CEA-Konfiguration
        if 'cea' not in config or 'mapping' not in config['cea']:
            raise ValueError("❌ CEA-Mapping-Konfiguration fehlt")
            
        mapping_config = config['cea']['mapping']
        
        # Validiere Mapping-Struktur
        if 'zone_mappings' not in mapping_config or 'typology_mappings' not in mapping_config:
            raise ValueError("❌ CEA-Mapping-Konfiguration fehlt erforderliche Mappings")
        
        # Logge verfügbare Spalten
        logger.info("📋 Verfügbare Spalten im Input:")
        for col in zone_gdf.columns:
            if col != 'geometry':
                logger.info(f"  - {col}")
        
        # Erstelle zone.shp
        zone_mappings = mapping_config['zone_mappings']
        zone_gdf_filtered = gpd.GeoDataFrame(geometry=zone_gdf.geometry)
        
        # Mappe und transformiere Felder
        for target_col, mapping in zone_mappings.items():
            try:
                if not isinstance(mapping, dict):
                    logger.warning(f"⚠️ Ungültiges Mapping für {target_col}: {mapping}")
                    continue
                    
                if 'sources' in mapping:
                    value_found = False
                    # Versuche Daten aus verschiedenen Quellen zu holen
                    for source, source_col in mapping['sources'].items():
                        if source_col in zone_gdf.columns:
                            zone_gdf_filtered[target_col] = zone_gdf[source_col]
                            value_found = True
                            logger.info(f"✅ {target_col} aus {source_col} gemappt")
                            break
                    
                    if not value_found:
                        logger.warning(f"⚠️ Keine gültige Quelle für {target_col} gefunden")
                        if 'default' in mapping:
                            default_value = mapping['default']
                            # Konvertiere Dictionary zu String
                            if isinstance(default_value, dict):
                                default_value = str(default_value)
                            zone_gdf_filtered[target_col] = default_value
                            logger.info(f"ℹ️ {target_col} mit Default-Wert {default_value} gesetzt")
                        continue
                        
                elif 'default' in mapping:
                    default_value = mapping['default']
                    # Konvertiere Dictionary zu String
                    if isinstance(default_value, dict):
                        default_value = str(default_value)
                    zone_gdf_filtered[target_col] = default_value
                    logger.info(f"ℹ️ {target_col} mit Default-Wert {default_value} gesetzt")
                else:
                    logger.warning(f"⚠️ Keine gültige Mapping-Konfiguration für {target_col}")
                    continue
                    
                # Wende Transformationen an
                if 'transformations' in mapping:
                    for transform in mapping['transformations']:
                        if transform == 'to_float':
                            zone_gdf_filtered[target_col] = pd.to_numeric(zone_gdf_filtered[target_col], errors='coerce')
                        elif transform == 'to_int':
                            zone_gdf_filtered[target_col] = pd.to_numeric(zone_gdf_filtered[target_col], errors='coerce').astype('Int64')
                        elif transform == 'to_string':
                            zone_gdf_filtered[target_col] = zone_gdf_filtered[target_col].astype(str)
                            
            except Exception as e:
                logger.error(f"❌ Fehler beim Mapping von {target_col}: {str(e)}")
                continue
        
        # Speichere zone.shp
        zone_output = output_dir / 'zone.shp'
        zone_gdf_filtered.to_file(zone_output)
        logger.info(f"✅ Zone-Datei gespeichert: {zone_output}")
        
        # Erstelle typology.shp
        typology_mappings = mapping_config['typology_mappings']
        typology_gdf = gpd.GeoDataFrame(geometry=zone_gdf.geometry)
        
        # Mappe und transformiere Felder für Typology
        for target_col, mapping in typology_mappings.items():
            try:
                if not isinstance(mapping, dict):
                    logger.warning(f"⚠️ Ungültiges Mapping für {target_col}: {mapping}")
                    continue
                    
                if 'sources' in mapping:
                    value_found = False
                    for source, source_col in mapping['sources'].items():
                        if source_col in zone_gdf.columns:
                            typology_gdf[target_col] = zone_gdf[source_col]
                            value_found = True
                            logger.info(f"✅ {target_col} aus {source_col} gemappt")
                            break
                    
                    if not value_found:
                        logger.warning(f"⚠️ Keine gültige Quelle für {target_col} gefunden")
                        if 'default' in mapping:
                            default_value = mapping['default']
                            # Konvertiere Dictionary zu String
                            if isinstance(default_value, dict):
                                default_value = str(default_value)
                            typology_gdf[target_col] = default_value
                            logger.info(f"ℹ️ {target_col} mit Default-Wert {default_value} gesetzt")
                        continue
                        
                elif 'default' in mapping:
                    default_value = mapping['default']
                    # Konvertiere Dictionary zu String
                    if isinstance(default_value, dict):
                        default_value = str(default_value)
                    typology_gdf[target_col] = default_value
                    logger.info(f"ℹ️ {target_col} mit Default-Wert {default_value} gesetzt")
                else:
                    logger.warning(f"⚠️ Keine gültige Mapping-Konfiguration für {target_col}")
                    continue
                    
                # Wende Transformationen an
                if 'transformations' in mapping:
                    for transform in mapping['transformations']:
                        if transform == 'to_float':
                            typology_gdf[target_col] = pd.to_numeric(typology_gdf[target_col], errors='coerce')
                        elif transform == 'to_int':
                            typology_gdf[target_col] = pd.to_numeric(typology_gdf[target_col], errors='coerce').astype('Int64')
                        elif transform == 'to_string':
                            typology_gdf[target_col] = typology_gdf[target_col].astype(str)
                            
            except Exception as e:
                logger.error(f"❌ Fehler beim Mapping von {target_col}: {str(e)}")
                continue
        
        # Speichere typology.shp
        typology_output = output_dir / 'typology.shp'
        typology_gdf.to_file(typology_output)
        logger.info(f"✅ Typology-Datei gespeichert: {typology_output}")
        
        logger.info("✅ CEA-Dateien erfolgreich erstellt")
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
        else:
            raise ValueError("❌ WFS-Konfiguration konnte nicht geladen werden")
            
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
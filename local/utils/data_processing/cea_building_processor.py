from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon
import logging
import re
import yaml
import sys

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent.parent
if str(local_dir) not in sys.path:
    sys.path.append(str(local_dir))

from utils.data_processing.base_building_processor import BuildingProcessorInterface
from utils.data_sources.fetch_osm_buildings import fetch_surrounding_buildings, process_osm_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets

class CEABuildingProcessor(BuildingProcessorInterface):
    """Konkrete Implementierung des BuildingProcessorInterface für CEA-Gebäudeverarbeitung"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den CEA Building Processor.
        
        Args:
            config (dict): Die Konfiguration mit Pfaden und Einstellungen
        """
        super().__init__(config)
        
        # Lade Metrik-Konfiguration
        metrics_config_path = Path(config.get('metrics_config', 'cfg/cea/building_metrics.yml'))
        self.metrics_config = self._load_metrics_config(metrics_config_path)
        
        # Lade CEA-Mapping-Konfiguration
        mapping_config_path = Path(config.get('cea_mapping', 'cfg/cea/cea_mapping.yml'))
        self.mapping_config = self._load_mapping_config(mapping_config_path)
        
    def _load_metrics_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Metrik-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Metrik-Konfiguration: {str(e)}")
            return {}
            
    def _load_mapping_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Mapping-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Mapping-Konfiguration: {str(e)}")
            return {}
    
    def process_cea_data(self, project_dir: Path) -> bool:
        """Verarbeitet die Daten für CEA.
        
        Args:
            project_dir (Path): Projektverzeichnis
            
        Returns:
            bool: True wenn erfolgreich verarbeitet
        """
        try:
            if self.site_polygon is None:
                self.logger.error("❌ Kein Site-Polygon verfügbar")
                return False
                
            # Erstelle Verzeichnisse
            geometry_dir = project_dir / 'inputs' / 'building-geometries'
            properties_dir = project_dir / 'inputs' / 'building-properties'
            networks_dir = project_dir / 'inputs' / 'networks'
            
            for directory in [geometry_dir, properties_dir, networks_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                
            # Speichere Site-Polygon
            site_path = geometry_dir / 'site.shp'
            site_gdf = gpd.GeoDataFrame({'geometry': [self.site_polygon]}, crs=self.config.get('crs', 'EPSG:31256'))
            site_gdf.to_file(site_path)
            self.logger.info(f"✅ Site-Polygon gespeichert: {site_path}")
            
            # Hole Umgebungsgebäude
            self.logger.info("🔄 Hole Umgebungsgebäude...")
            surroundings_gdf = fetch_surrounding_buildings(
                self.site_polygon,
                self.config.get('osm', {})
            )
            
            if surroundings_gdf is not None:
                # Verarbeite Umgebungsgebäude
                surroundings_gdf = process_osm_buildings(
                    surroundings_gdf,
                    self.config.get('osm', {}).get('building_defaults', {})
                )
                
                # Validiere Umgebungsgebäude
                surroundings_gdf = self._validate_and_repair_geometries(surroundings_gdf)
                
                # Speichere Umgebungsgebäude
                surroundings_path = geometry_dir / 'surroundings.shp'
                surroundings_gdf.to_file(surroundings_path)
                self.logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gespeichert: {surroundings_path}")
            
            # Hole Straßen
            self.logger.info("🔄 Hole Straßen...")
            streets_gdf = fetch_osm_streets(
                self.site_polygon,
                self.config.get('osm', {}).get('street_tags', [])
            )
            
            if streets_gdf is not None:
                streets_path = networks_dir / 'streets.shp'
                streets_gdf.to_file(streets_path)
                self.logger.info(f"✅ {len(streets_gdf)} Straßen gespeichert: {streets_path}")
            
            # Erstelle CEA-Dateien
            self.create_cea_files(project_dir)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CEA-Datenverarbeitung: {str(e)}")
            return False

    def create_cea_files(self, project_dir: Path) -> bool:
        """Erstellt die CEA-Dateien (zone.shp und typology.dbf).
        
        Args:
            project_dir (Path): Projektverzeichnis
            
        Returns:
            bool: True wenn erfolgreich erstellt
        """
        try:
            if self.buildings_gdf is None:
                self.logger.error("❌ Keine Gebäudedaten verfügbar")
                return False
            
            # Erstelle zone.shp
            zone_mappings = self.mapping_config['zone_shp']['mappings']
            zone_gdf = self.buildings_gdf.copy()
            
            # Mappe Felder für zone.shp
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
                    # Setze Standardwerte für fehlende Spalten
                    if transform_type == 'int':
                        zone_gdf[target_col] = 0
                    elif transform_type == 'float':
                        zone_gdf[target_col] = 0.0
                    else:
                        zone_gdf[target_col] = ''
            
            # Speichere zone.shp
            zone_path = project_dir / 'inputs' / 'building-geometry' / 'zone.shp'
            zone_gdf.to_file(zone_path)
            self.logger.info(f"✅ zone.shp erstellt: {zone_path}")
            
            # Erstelle typology.dbf
            typology_mappings = self.mapping_config['typology_dbf']['mappings']
            typology_df = pd.DataFrame()
            
            # Mappe Felder für typology.dbf
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
                    # Setze Standardwerte für fehlende Spalten
                    if transform_type == 'int':
                        typology_df[target_col] = 0
                    elif transform_type == 'float':
                        typology_df[target_col] = 0.0
                    else:
                        typology_df[target_col] = ''
            
            # Speichere typology.dbf
            typology_path = project_dir / 'inputs' / 'building-properties' / 'typology.dbf'
            typology_df.to_dbf(typology_path)
            self.logger.info(f"✅ typology.dbf erstellt: {typology_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen der CEA-Dateien: {str(e)}")
            return False
    
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Validiert die Gebäudedaten basierend auf der Konfiguration."""
        try:
            # Prüfe ob alle erforderlichen Felder vorhanden sind
            required_fields = self.metrics_config.get('required_fields', [])
        for field in required_fields:
            if field not in building_data:
                    self.logger.warning(f"⚠️ Pflichtfeld fehlt: {field}")
                    return False
            
            # Prüfe ob Geometrie gültig ist
            if not building_data['geometry'].is_valid:
                self.logger.warning("⚠️ Ungültige Geometrie")
                return False
            
        return True

        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Gebäudevalidierung: {str(e)}")
            return False
    
    def process_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein einzelnes Gebäude."""
        try:
            # Kopiere Basisdaten
            processed_data = building_data.copy()
            
            # Füge Metadaten hinzu
            processed_data['data_source'] = 'CityGML'
            processed_data['processing_date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
            
            return processed_data
            
    except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return building_data 
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon
import logging
import re
import yaml
from simpledbf import Dbf5

from .base_building_processor import BuildingProcessorInterface
from ..data_sources.fetch_osm_buildings import fetch_surrounding_buildings, process_osm_buildings
from ..data_sources.fetch_osm_streets import fetch_osm_streets

class CEABuildingProcessor(BuildingProcessorInterface):
    """Konkrete Implementierung des BuildingProcessorInterface für CEA-Gebäudeverarbeitung"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den CEA Building Processor.
        
        Args:
            config (dict): Die Konfiguration mit Pfaden und Einstellungen
        """
        super().__init__(config)
        
        # Lade Metrik-Konfiguration
        metrics_config_path = Path(self.config.get('paths', {}).get('config', 'local/cfg/cea')) / 'building_metrics.yml'
        self.metrics_config = self._load_metrics_config(metrics_config_path)
        
        # Lade CEA-Mapping-Konfiguration
        mapping_config_path = Path(self.config.get('paths', {}).get('config', 'local/cfg/cea')) / 'cea_mapping.yml'
        self.mapping_config = self._load_mapping_config(mapping_config_path)
        
        if not self.mapping_config:
            self.logger.error("❌ Keine gültige Mapping-Konfiguration gefunden")
            
    def _load_metrics_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Metrik-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # Validiere Konfiguration
            required_sections = ['required_fields', 'metrics']
            for section in required_sections:
                if section not in config:
                    self.logger.error(f"❌ Fehlender Abschnitt in Metrik-Konfiguration: {section}")
                    return {}
                    
            return config
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Metrik-Konfiguration: {str(e)}")
            return {}
            
    def _load_mapping_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Mapping-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # Validiere Konfiguration
            required_sections = ['zone_shp', 'typology_dbf']
            for section in required_sections:
                if section not in config:
                    self.logger.error(f"❌ Fehlender Abschnitt in Mapping-Konfiguration: {section}")
                    return {}
                    
            return config
            
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
            
            if not self.mapping_config:
                self.logger.error("❌ Keine Mapping-Konfiguration verfügbar")
                return False
            
            # Erstelle zone.shp
            zone_mappings = self.mapping_config.get('zone_shp', {}).get('mappings', {})
            zone_gdf = self.buildings_gdf.copy()
            
            # Mappe Felder für zone.shp
            for target_col, mapping in zone_mappings.items():
                source_col = mapping.get('source')
                transform_type = mapping.get('transform', 'str')
                default_value = mapping.get('default')
                
                if source_col in zone_gdf.columns:
                    if transform_type == 'int':
                        zone_gdf[target_col] = pd.to_numeric(zone_gdf[source_col], errors='coerce').fillna(default_value or 0).astype(int)
                    elif transform_type == 'float':
                        zone_gdf[target_col] = pd.to_numeric(zone_gdf[source_col], errors='coerce').fillna(default_value or 0.0).astype(float)
                    else:
                        zone_gdf[target_col] = zone_gdf[source_col].fillna(default_value or '').astype(str)
                else:
                    # Setze Standardwerte für fehlende Spalten
                    if transform_type == 'int':
                        zone_gdf[target_col] = default_value or 0
                    elif transform_type == 'float':
                        zone_gdf[target_col] = default_value or 0.0
                    else:
                        zone_gdf[target_col] = default_value or ''
            
            # Validiere zone.shp Daten
            required_zone_fields = self.mapping_config.get('zone_shp', {}).get('required_fields', [])
            for field in required_zone_fields:
                if field not in zone_gdf.columns:
                    self.logger.error(f"❌ Pflichtfeld fehlt in zone.shp: {field}")
                    return False
            
            # Speichere zone.shp
            zone_path = project_dir / 'inputs' / 'building-geometries' / 'zone.shp'
            zone_gdf.to_file(zone_path)
            self.logger.info(f"✅ zone.shp erstellt mit {len(zone_gdf)} Gebäuden: {zone_path}")
            
            # Erstelle typology.dbf
            typology_mappings = self.mapping_config.get('typology_dbf', {}).get('mappings', {})
            typology_data = {}
            
            # Mappe Felder für typology.dbf
            for target_col, mapping in typology_mappings.items():
                source_col = mapping.get('source')
                transform_type = mapping.get('transform', 'str')
                default_value = mapping.get('default')
                
                if source_col in zone_gdf.columns:
                    if transform_type == 'int':
                        typology_data[target_col] = pd.to_numeric(zone_gdf[source_col], errors='coerce').fillna(default_value or 0).astype(int)
                    elif transform_type == 'float':
                        typology_data[target_col] = pd.to_numeric(zone_gdf[source_col], errors='coerce').fillna(default_value or 0.0).astype(float)
                    else:
                        typology_data[target_col] = zone_gdf[source_col].fillna(default_value or '').astype(str)
                else:
                    # Setze Standardwerte für fehlende Spalten
                    if transform_type == 'int':
                        typology_data[target_col] = pd.Series([default_value or 0] * len(zone_gdf))
                    elif transform_type == 'float':
                        typology_data[target_col] = pd.Series([default_value or 0.0] * len(zone_gdf))
                    else:
                        typology_data[target_col] = pd.Series([default_value or ''] * len(zone_gdf))
            
            # Validiere typology.dbf Daten
            required_typology_fields = self.mapping_config.get('typology_dbf', {}).get('required_fields', [])
            for field in required_typology_fields:
                if field not in typology_data:
                    self.logger.error(f"❌ Pflichtfeld fehlt in typology.dbf: {field}")
                    return False
            
            # Erstelle DataFrame und speichere als DBF
            typology_df = pd.DataFrame(typology_data)
            typology_path = project_dir / 'inputs' / 'building-properties' / 'typology.dbf'
            
            # Konvertiere zu DBF mit simpledbf
            dbf = Dbf5()
            dbf.from_dataframe(typology_df)
            dbf.save(str(typology_path))
            
            self.logger.info(f"✅ typology.dbf erstellt mit {len(typology_df)} Einträgen: {typology_path}")
            
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
            
            # Prüfe Metrik-Bedingungen
            metrics = self.metrics_config.get('metrics', {})
            for metric_name, conditions in metrics.items():
                if metric_name not in building_data:
                    continue
                    
                value = building_data[metric_name]
                
                # Prüfe Minimum
                if 'min' in conditions and value < conditions['min']:
                    self.logger.warning(f"⚠️ {metric_name} unter Minimum: {value} < {conditions['min']}")
                    return False
                
                # Prüfe Maximum
                if 'max' in conditions and value > conditions['max']:
                    self.logger.warning(f"⚠️ {metric_name} über Maximum: {value} > {conditions['max']}")
                    return False
                
                # Prüfe erlaubte Werte
                if 'allowed_values' in conditions and value not in conditions['allowed_values']:
                    self.logger.warning(f"⚠️ {metric_name} nicht erlaubt: {value}")
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
            
            # Verarbeite BuildingParts wenn vorhanden
            if processed_data.get('has_building_parts', False):
                part_count = processed_data.get('building_parts_count', 0)
                self.logger.info(f"🏗️ Verarbeite Gebäude mit {part_count} BuildingParts")
                
                # Berechne zusammengesetzte Metriken
                if isinstance(processed_data['geometry'], MultiPolygon):
                    # Berechne Gesamtfläche
                    total_area = sum(polygon.area for polygon in processed_data['geometry'].geoms)
                    processed_data['total_area'] = total_area
                    
                    # Berechne durchschnittliche Höhe
                    heights = []
                    for attr in processed_data.keys():
                        if attr.startswith('part_') and attr.endswith('_height'):
                            if pd.notnull(processed_data[attr]):
                                heights.append(float(processed_data[attr]))
                    
                    if heights:
                        processed_data['avg_height'] = np.mean(heights)
            
            return processed_data
            
        except Exception as e:
            self.logger.warning(f"⚠️ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return building_data 
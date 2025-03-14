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

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        # Lade WFS-Konfiguration für Mappings
        self.wfs_config = config.get('vienna_wfs', {})
        
    def _load_metrics_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Metrik-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Metrik-Konfiguration: {str(e)}")
            return {}
            
    def _load_mapping_config(self, config_path: Path) -> Dict[str, Any]:
        """Lädt die Mapping-Konfiguration aus der YAML-Datei."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Mapping-Konfiguration: {str(e)}")
            return {}
    
    def process_cea_data(self, project_dir: Path) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Verarbeitet die Daten für CEA.
        
        Args:
            project_dir (Path): Projektverzeichnis
            
        Returns:
            tuple[bool, Optional[Dict[str, Any]]]: (Erfolg, Verarbeitete Daten)
        """
        try:
            if self.site_polygon is None or self.buildings_gdf is None:
                logger.error("❌ Keine Site-Polygon oder Gebäudedaten verfügbar")
                return False, None
                
            # Erstelle Verzeichnisstruktur
            geometry_dir = project_dir / 'inputs' / 'building-geometry'
            properties_dir = project_dir / 'inputs' / 'building-properties'
            networks_dir = project_dir / 'inputs' / 'networks'
            
            for directory in [geometry_dir, properties_dir, networks_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                
            # 1. Speichere Site-Polygon
            site_path = geometry_dir / 'site.shp'
            site_gdf = gpd.GeoDataFrame({'geometry': [self.site_polygon]}, crs=self.config.get('crs', 'EPSG:31256'))
            site_gdf.to_file(site_path)
            logger.info(f"✅ Site-Polygon gespeichert: {site_path}")
            
            # 2. Erstelle CEA-Dateien (zone.shp und typology.dbf)
            zone_gdf, typology_df = self._create_cea_files(geometry_dir, properties_dir)
            if zone_gdf is None or typology_df is None:
                return False, None
            
            # 3. Hole und speichere Umgebungsgebäude
            logger.info("🔄 Hole Umgebungsgebäude...")
            surroundings_gdf = fetch_surrounding_buildings(
                self.site_polygon,
                self.config.get('osm', {})
            )
            
            if surroundings_gdf is not None:
                surroundings_gdf = process_osm_buildings(
                    surroundings_gdf,
                    self.config.get('osm', {}).get('building_defaults', {})
                )
                surroundings_path = geometry_dir / 'surroundings.shp'
                surroundings_gdf.to_file(surroundings_path)
                logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gespeichert: {surroundings_path}")
            
            # 4. Hole und speichere Straßen
            logger.info("🔄 Hole Straßen...")
            streets_gdf = fetch_osm_streets(
                self.site_polygon,
                self.config.get('osm', {}).get('street_tags', [])
            )
            
            if streets_gdf is not None:
                streets_path = networks_dir / 'streets.shp'
                streets_gdf.to_file(streets_path)
                logger.info(f"✅ {len(streets_gdf)} Straßen gespeichert: {streets_path}")
            
            # Erstelle Ausgabe-Dictionary
            output_data = {
                'zone': zone_gdf,
                'typology': typology_df,
                'surroundings': surroundings_gdf,
                'streets': streets_gdf,
                'site': site_gdf
            }
            
            return True, output_data
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der CEA-Datenverarbeitung: {str(e)}")
            return False, None

    def _map_construction_period(self, period: str) -> str:
        """Mappt eine Bauperiode auf einen CEA-Zeitcode.
        
        Args:
            period (str): Bauperiode aus WFS (z.B. "1848 - 1918")
            
        Returns:
            str: CEA-Zeitcode (z.B. "_A" oder "_B")
        """
        try:
            periods = self.wfs_config.get('periods', {})
            for period_range, mapping in periods.items():
                if period == period_range:
                    # Wähle zufällig eine Kategorie aus den verfügbaren
                    categories = mapping.get('categories', [])
                    if categories:
                        return np.random.choice(categories)
            return "_A"  # Fallback wenn keine Zuordnung gefunden
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping der Bauperiode: {str(e)}")
            return "_A"
    
    def _map_building_type(self, building_type: str) -> str:
        """Mappt einen Gebäudetyp auf einen CEA-Typ.
        
        Args:
            building_type (str): Gebäudetyp aus WFS
            
        Returns:
            str: CEA-Gebäudetyp (SFH, MFH, AB, TH, HR)
        """
        try:
            building_types = self.wfs_config.get('building_types', {})
            return building_types.get(building_type, "MFH")  # MFH als Fallback
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping des Gebäudetyps: {str(e)}")
            return "MFH"
    
    def _create_standard_value(self, period: str, building_type: str) -> str:
        """Erstellt den STANDARD-Wert für die typology.dbf.
        
        Args:
            period (str): Bauperiode aus WFS
            building_type (str): Gebäudetyp aus WFS
            
        Returns:
            str: STANDARD-Wert (z.B. "MFH_A")
        """
        try:
            cea_type = self._map_building_type(building_type)
            cea_period = self._map_construction_period(period)
            return f"{cea_type}{cea_period}"
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen des STANDARD-Werts: {str(e)}")
            return "MFH_A"  # Fallback-Wert

    def _create_cea_files(self, geometry_dir: Path, properties_dir: Path) -> tuple[Optional[gpd.GeoDataFrame], Optional[pd.DataFrame]]:
        """Erstellt die CEA-Dateien (zone.shp und typology.dbf).
        
        Args:
            geometry_dir (Path): Verzeichnis für Geometriedaten
            properties_dir (Path): Verzeichnis für Eigenschaftendaten
            
        Returns:
            tuple[Optional[gpd.GeoDataFrame], Optional[pd.DataFrame]]: (zone_gdf, typology_df) oder (None, None) bei Fehler
        """
        try:
            # 1. Erstelle zone.shp
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
            zone_path = geometry_dir / 'zone.shp'
            zone_gdf.to_file(zone_path)
            logger.info(f"✅ zone.shp erstellt: {zone_path}")
            
            # 2. Erstelle typology.dbf
            typology_df = pd.DataFrame()
            
            # Hole Bauperiode und Gebäudetyp aus WFS-Daten
            construction_periods = zone_gdf['Gebäudeinfo_L_BAUJ'].fillna('nach 1945')
            building_types = zone_gdf['Gebäudetypologie_OBJ_STR_TXT'].fillna('W2.1.-Bürgerhaus-kleine Haustypen ohne Hof')
            
            # Erstelle STANDARD-Werte
            typology_df['STANDARD'] = [
                self._create_standard_value(period, btype) 
                for period, btype in zip(construction_periods, building_types)
            ]
            
            # Mappe andere Felder für typology.dbf
            typology_mappings = self.mapping_config['typology_dbf']['mappings']
            for target_col, mapping in typology_mappings.items():
                if target_col != 'STANDARD':  # STANDARD wurde bereits gesetzt
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
            typology_path = properties_dir / 'typology.dbf'
            typology_df.to_dbf(typology_path)
            logger.info(f"✅ typology.dbf erstellt: {typology_path}")
            
            return zone_gdf, typology_df
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen der CEA-Dateien: {str(e)}")
            return None, None
    
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Validiert die Gebäudedaten basierend auf der Konfiguration."""
        try:
            # Prüfe ob alle erforderlichen Felder vorhanden sind
            required_fields = self.metrics_config.get('required_fields', [])
            for field in required_fields:
                if field not in building_data:
                    logger.warning(f"⚠️ Pflichtfeld fehlt: {field}")
                    return False
            
            # Prüfe ob Geometrie gültig ist
            if not building_data['geometry'].is_valid:
                logger.warning("⚠️ Ungültige Geometrie")
                return False
            
            return True
        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der Gebäudevalidierung: {str(e)}")
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
            logger.warning(f"⚠️ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return building_data 
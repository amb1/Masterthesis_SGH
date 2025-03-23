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
from core.config_manager import load_config

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from pipeline.processing.base_processor import BuildingProcessorInterface
from pipeline.data_sources.osm_building_fetcher import fetch_surrounding_buildings, process_osm_buildings
from pipeline.data_sources.osm_street_fetcher import fetch_osm_streets
from pipeline.data_sources.wfs_fetcher import ViennaWFS

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CEABuildingProcessor(BuildingProcessorInterface):
    """CEA-spezifischer Gebäudeprozessor."""
    
    def __init__(self, cea_config, project_config=None):
        """Initialisiert den CEA Building Processor.
        
        Args:
            cea_config: CEA-spezifische Konfiguration
            project_config: Optionale Projekt-Konfiguration
        """
        super().__init__(project_config)
        
        # Verwende die übergebene CEA-Konfiguration
        if isinstance(cea_config, dict) and cea_config.get('cea'):
            self.cea_config = cea_config['cea']
        else:
            # Versuche die Konfiguration aus einer Datei zu laden
            self.cea_config = self._load_specific_config('cea')
            
        if not self.cea_config:
            raise ValueError("❌ Keine gültige CEA-Konfiguration gefunden")
            
        # Initialisiere die Konfigurationen
        self.mapping_config = self.cea_config.get('mapping', {})
        self.metrics_config = self.cea_config.get('metrics', {})
        self.output_config = self.cea_config.get('output', {})
        
        # Setze Standardwerte
        if 'defaults' not in self.mapping_config:
            self.mapping_config['defaults'] = {
                'floors_ag': 4,
                'floors_bg': 1,
                'year': 1960,
                'use_type': 'NONE'
            }
            
        logger.info("✅ CEA-Konfiguration geladen")
        
    def process_cea_data(self, output_dir):
        """Verarbeitet die Gebäudedaten für CEA."""
        try:
            # Implementiere CEA-spezifische Verarbeitung
            logger.info("🔄 Starte CEA-Verarbeitung")
            
            # TODO: Implementiere CEA-Verarbeitung
            
            logger.info("✅ CEA-Verarbeitung abgeschlossen")
            return True, None
            
        except Exception as e:
            logger.error(f"❌ Fehler bei CEA-Verarbeitung: {str(e)}")
            return False, None

    def _map_construction_period(self, period: str) -> str:
        """Mappt eine Bauperiode auf einen CEA-Zeitcode.
        
        Args:
            period (str): Bauperiode aus WFS (z.B. "1848 - 1918")
            
        Returns:
            str: CEA-Zeitcode (z.B. "_A" oder "_B")
        """
        try:
            periods = self.mapping_config.get('periods', {})
            if period in periods:
                categories = periods[period].get('categories', [])
                if categories:
                    return categories[0]  # Nehme den ersten Wert statt zufällig
            return ""  # Fallback wenn keine Zuordnung gefunden
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping der Bauperiode: {str(e)}")
            return ""

    def _get_year_from_period(self, period: str) -> int:
        """Berechnet das Jahr basierend auf der Bauperiode.
        
        Args:
            period (str): Bauperiode aus WFS
            
        Returns:
            int: Geschätztes Baujahr
        """
        try:
            periods = self.mapping_config.get('periods', {})
            if period in periods:
                return periods[period].get('default_year', 1960)
            return 1960  # Fallback
        except Exception as e:
            logger.error(f"❌ Fehler bei der Berechnung des Baujahrs: {str(e)}")
            return 1960

    def _map_building_type(self, building_type: str) -> str:
        """Mappt einen Gebäudetyp auf einen CEA-Typ.
        
        Args:
            building_type (str): Gebäudetyp aus WFS
            
        Returns:
            str: CEA-Gebäudetyp (SFH, MFH, AB, TH, HR)
        """
        try:
            building_types = self.mapping_config.get('building_types', {}).get('standard_prefix', {})
            return building_types.get(building_type, "NONE")  # NONE als Fallback
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping des Gebäudetyps: {str(e)}")
            return "NONE"
    
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
            return f"{cea_type}{cea_period}" if cea_period else cea_type
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen des STANDARD-Werts: {str(e)}")
            return "NONE"  # Fallback-Wert

    def _create_cea_files(self, geometry_dir: Path, properties_dir: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Erstellt die CEA-Dateien (zone.shp und typology.shp).
        
        Args:
            geometry_dir (Path): Verzeichnis für Geometrie-Dateien
            properties_dir (Path): Verzeichnis für Eigenschafts-Dateien
            
        Returns:
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: (zone_gdf, typology_gdf)
        """
        try:
            # Erstelle leere GeoDataFrames mit Beispieldaten
            geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
            zone_data = {
                'geometry': [geometry],
                'Name': ['Building1'],
                'floors_ag': [4],
                'floors_bg': [1],
                'height_ag': [12.0],
                'height_bg': [3.0]
            }
            zone_gdf = gpd.GeoDataFrame(zone_data, crs=self.project_config.get('crs', 'EPSG:31256'))

            typology_data = {
                'Name': ['Building1'],
                'STANDARD': ['MFH_A'],
                'YEAR': [1960],
                'USE_TYPE': ['MFH']
            }
            typology_gdf = gpd.GeoDataFrame(typology_data)

            return zone_gdf, typology_gdf

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
        """Verarbeitet ein einzelnes Gebäude.
        
        Args:
            building_data: Dictionary mit Gebäudedaten
            
        Returns:
            Dict[str, Any]: Verarbeitete Gebäudedaten
        """
        try:
            if not self.validate_building(building_data):
                return building_data

            # Kopiere die Eingabedaten
            processed_data = building_data.copy()

            # Berechne floors_ag basierend auf measured_height
            if 'measured_height' in processed_data:
                processed_data['floors_ag'] = int(processed_data['measured_height'] / 3)

            # Setze floors_bg basierend auf NS
            if 'NS' in processed_data:
                mapping = {'1': 1, '2': 2}
                processed_data['floors_bg'] = mapping.get(processed_data['NS'], 1)

            # Setze year basierend auf L_BAUJ oder OBJ_STR2_TXT
            if 'L_BAUJ' in processed_data:
                processed_data['year'] = processed_data['L_BAUJ']
            elif 'OBJ_STR2_TXT' in processed_data:
                processed_data['year'] = self._get_year_from_period(processed_data['OBJ_STR2_TXT'])

            # Setze use_type basierend auf L_BAUTYP
            if 'L_BAUTYP' in processed_data:
                processed_data['use_type'] = self._map_building_type(processed_data['L_BAUTYP'])

            return processed_data

        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return building_data

    def _load_required_fields(self) -> Dict[str, List[str]]:
        """Lädt die erforderlichen Felder aus der Konfiguration"""
        try:
            cea_fields = self.config.get('fields', {})
            return {
                'zone.shp': cea_fields.get('zone_shp', {}).get('fields', {}).keys(),
                'typology.dbf': cea_fields.get('typology_dbf', {}).get('fields', {}).keys()
            }
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der erforderlichen Felder: {str(e)}")
            return {}
            
    def validate_geometry(self, gdf: gpd.GeoDataFrame, required_types: List[str]) -> bool:
        """Validiert die Geometrie eines GeoDataFrames"""
        try:
            if gdf is None or gdf.empty:
                logger.error("❌ GeoDataFrame ist leer")
                return False
                
            if 'geometry' not in gdf.columns:
                logger.error("❌ Keine Geometriespalte gefunden")
                return False
                
            # Prüfe Geometrietypen
            geometry_types = gdf.geometry.type.unique()
            invalid_types = [t for t in geometry_types if t not in required_types]
            
            if invalid_types:
                logger.error(f"❌ Ungültige Geometrietypen gefunden: {invalid_types}")
                return False
                
            # Prüfe auf ungültige Geometrien
            invalid_geometries = gdf[~gdf.geometry.is_valid]
            if not invalid_geometries.empty:
                logger.error(f"❌ {len(invalid_geometries)} ungültige Geometrien gefunden")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return False
            
    def validate_fields(self, gdf: gpd.GeoDataFrame, required_fields: List[str]) -> bool:
        """Validiert die Felder eines GeoDataFrames"""
        try:
            if gdf is None or gdf.empty:
                logger.error("❌ GeoDataFrame ist leer")
                return False
                
            # Prüfe erforderliche Felder
            missing_fields = [field for field in required_fields if field not in gdf.columns]
            if missing_fields:
                logger.error(f"❌ Fehlende Felder: {missing_fields}")
                return False
                
            # Prüfe auf NULL-Werte in erforderlichen Feldern
            for field in required_fields:
                null_count = gdf[field].isnull().sum()
                if null_count > 0:
                    logger.warning(f"⚠️ {null_count} NULL-Werte im Feld {field}")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Feldvalidierung: {str(e)}")
            return False
            
    def validate_crs(self, gdf: gpd.GeoDataFrame, required_crs: str) -> bool:
        """Validiert das Koordinatenreferenzsystem"""
        try:
            if gdf is None or gdf.empty:
                logger.error("❌ GeoDataFrame ist leer")
                return False
                
            if gdf.crs is None:
                logger.error("❌ Kein CRS definiert")
                return False
                
            if str(gdf.crs) != required_crs:
                logger.error(f"❌ Falsches CRS: {gdf.crs} (erwartet: {required_crs})")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der CRS-Validierung: {str(e)}")
            return False
            
    def validate_building_data(self, building_data: Dict[str, Any]) -> bool:
        """Validiert die Gebäudedaten"""
        try:
            # Überprüfe erforderliche Felder
            for field in self.required_fields['zone.shp']:
                if field not in building_data:
                    logger.warning(f"⚠️ Fehlendes Feld in Gebäude: {field}")
                    return False
                    
            # Validiere Datentypen
            if not self._validate_data_types(building_data):
                return False
                
            # Validiere Geometrie
            if not self._validate_geometry(building_data):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Gebäudevalidierung: {str(e)}")
            return False
            
    def _validate_data_types(self, building_data: Dict[str, Any]) -> bool:
        """Überprüft die Datentypen der Felder"""
        try:
            type_mapping = {
                'floors_ag': int,
                'floors_bg': int,
                'height_ag': float,
                'height_bg': float,
                'YEAR': int,
                'USE1_R': float,
                'USE2_R': float,
                'USE3_R': float
            }
            
            for field, expected_type in type_mapping.items():
                if field in building_data:
                    try:
                        expected_type(building_data[field])
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ Ungültiger Datentyp für {field}")
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Datentypvalidierung: {str(e)}")
            return False
            
    def _validate_geometry(self, building_data: Dict[str, Any]) -> bool:
        """Überprüft die Geometrie des Gebäudes"""
        try:
            if 'geometry' not in building_data:
                logger.warning("⚠️ Keine Geometrie vorhanden")
                return False
                
            geometry = building_data['geometry']
            if not hasattr(geometry, 'is_valid'):
                logger.warning("⚠️ Ungültiges Geometrieformat")
                return False
                
            if not geometry.is_valid:
                logger.warning("⚠️ Ungültige Geometrie")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return False

def get_year_and_suffix(period: str, config: Dict[str, Any]) -> tuple[int, str]:
    """Extrahiert Jahr und Suffix aus einer Bauperiode.
    
    Args:
        period (str): Bauperiode (z.B. "1848-1918")
        config (Dict[str, Any]): CEA-Konfiguration
        
    Returns:
        tuple[int, str]: (Jahr, Suffix)
    """
    try:
        # Extrahiere Start- und Endjahr
        years = re.findall(r'\d{4}', period)
        if len(years) >= 2:
            start_year = int(years[0])
            end_year = int(years[1])
            year = (start_year + end_year) // 2
        else:
            year = int(years[0]) if years else 1960
            
        # Finde passenden Suffix
        building_periods = config.get('building_periods', [])
        for period_config in building_periods:
            if period_config['start'] <= year <= period_config['end']:
                return year, period_config['suffix']
                
        return year, '_A'  # Fallback
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Extrahieren von Jahr und Suffix: {str(e)}")
        return 1960, '_A'

def adjust_field_widths(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Passt die Feldbreiten für Shapefile-Export an.
    
    Args:
        gdf (gpd.GeoDataFrame): Input GeoDataFrame
        
    Returns:
        gpd.GeoDataFrame: Angepasster GeoDataFrame
    """
    try:
        # Kopiere DataFrame
        adjusted = gdf.copy()
        
        # Kürze Text-Felder auf max. 254 Zeichen (Shapefile-Limit)
        for col in adjusted.select_dtypes(include=['object']).columns:
            if col != 'geometry':
                adjusted[col] = adjusted[col].astype(str).str.slice(0, 254)
                
        # Konvertiere numerische Felder
        for col in adjusted.select_dtypes(include=['int64', 'float64']).columns:
            if col != 'geometry':
                # Integer zu Float für bessere Kompatibilität
                adjusted[col] = adjusted[col].astype(float)
                
        return adjusted
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Anpassen der Feldbreiten: {str(e)}")
        return gdf

def enrich_building_data(buildings_gdf: gpd.GeoDataFrame, wfs_data: Dict[str, gpd.GeoDataFrame]) -> gpd.GeoDataFrame:
    """Reichert Gebäudedaten mit WFS-Daten an.
    
    Args:
        buildings_gdf (gpd.GeoDataFrame): Gebäude-GeoDataFrame
        wfs_data (Dict[str, gpd.GeoDataFrame]): WFS-Layer-Daten
        
    Returns:
        gpd.GeoDataFrame: Angereicherter GeoDataFrame
    """
    try:
        # Kopiere DataFrame
        enriched = buildings_gdf.copy()
        
        # Füge WFS-Daten hinzu
        for layer_name, layer_data in wfs_data.items():
            if layer_data is not None and not layer_data.empty:
                try:
                    # Räumliche Verknüpfung
                    joined = gpd.sjoin_nearest(
                        enriched,
                        layer_data,
                        how='left',
                        distance_col='distance'
                    )
                    
                    # Füge relevante Spalten hinzu
                    for col in layer_data.columns:
                        if col not in ['geometry', 'index', 'index_right']:
                            enriched[f"{layer_name}_{col}"] = joined[col]
                            
                    logger.info(f"✅ WFS-Layer {layer_name} hinzugefügt")
                except Exception as e:
                    logger.warning(f"⚠️ Fehler beim Hinzufügen von Layer {layer_name}: {str(e)}")
                    
        return enriched
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Anreichern der Gebäudedaten: {str(e)}")
        return buildings_gdf 
"""
CEA-Prozessor für die Verarbeitung von Gebäudedaten für City Energy Analyst.

Dieser Prozessor implementiert die spezifische Verarbeitung von Gebäudedaten
für die CEA-Analyse.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon, MultiPolygon
import logging
import re
import yaml
import sys
from core.config_manager import load_config
from pipeline.processing.base_processor import BuildingProcessorInterface, BaseProcessor
from pipeline.data_sources.osm_fetcher import OSMFetcher, fetch_osm_data
from pipeline.data_sources.wfs_fetcher import ViennaWFSFetcher
from pipeline.processing.mapping_processor import MappingProcessor
from lxml import etree

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CEAMapper:
    """Mapper für CEA-Felder aus verschiedenen Datenquellen."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den CEA-Mapper.
        
        Args:
            config: Mapping-Konfiguration mit Feldmappings und Validierungsregeln
        """
        self.config = config
        self.validation_rules = config.get("validation", {})
        self.field_mappings = config.get("mappings", {})
        
    def map_field(self, field_name: str, data: Union[dict, etree._Element], source: str) -> Any:
        """Mapped ein Feld aus den Quelldaten.
        
        Args:
            field_name: Name des Zielfelds
            data: Quelldaten (Dict für WFS, XML für CityGML)
            source: Datenquelle ('wfs' oder 'citygml')
            
        Returns:
            Gemappter Wert für das Feld
        """
        if field_name not in self.field_mappings:
            return None
            
        mapping = self.field_mappings[field_name]
        source_mapping = mapping.get(source, {})
        
        if source == "citygml":
            return self._map_citygml_field(field_name, data, source_mapping)
        else:
            return self._map_wfs_field(field_name, data, source_mapping)
    
    def _map_citygml_field(self, field_name: str, xml: etree._Element, mapping: Dict[str, Any]) -> Any:
        """Mapped ein Feld aus CityGML-Daten.
        
        Args:
            field_name: Name des Zielfelds
            xml: CityGML XML-Element
            mapping: Mapping-Konfiguration für das Feld
            
        Returns:
            Gemappter Wert
        """
        xpath = mapping.get("xpath")
        if not xpath:
            return None
            
        # Spezialfall für Name-Generierung
        if field_name == "Name":
            street = xml.xpath(".//xAL:StreetNameElement/text()", namespaces={"xAL": "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"})[0]
            number = xml.xpath(".//xAL:BuildingNumber/text()", namespaces={"xAL": "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"})[0]
            return f"{street}_{number}"
            
        # Spezialfall für REFERENCE
        if field_name == "REFERENCE":
            return xml.get("{http://www.opengis.net/gml}id")
            
        try:
            value = xml.xpath(xpath, namespaces={"bldg": "http://www.opengis.net/citygml/building/2.0"})[0]
            return self._convert_value(value, mapping.get("type", "str"))
        except (IndexError, ValueError):
            return mapping.get("default")
    
    def _map_wfs_field(self, field_name: str, data: Dict[str, Any], mapping: Dict[str, Any]) -> Any:
        """Mapped ein Feld aus WFS-Daten.
        
        Args:
            field_name: Name des Zielfelds
            data: WFS-Feature-Daten
            mapping: Mapping-Konfiguration für das Feld
            
        Returns:
            Gemappter Wert
        """
        source_field = mapping.get("field")
        if not source_field:
            return None
            
        # Spezialfall für Name-Generierung
        if field_name == "Name":
            street = data.get("Gebäudeinfo_STRNAML", "")
            number = data.get("Gebäudeinfo_VONN", "")
            return f"{street}_{number}"
            
        # Spezialfall für Nutzungstypen
        if field_name in ["1ST_USE", "2ND_USE", "3RD_USE"]:
            usage_field = f"Gebäudeinfo_L_NUTZUNG{'' if field_name == '1ST_USE' else field_name[0]}"
            usage = data.get(usage_field, "")
            return self._map_usage_type(usage)
            
        value = data.get(source_field)
        if value is None:
            return mapping.get("default")
            
        return self._convert_value(value, mapping.get("type", "str"))
    
    def _convert_value(self, value: Any, target_type: str) -> Any:
        """Konvertiert einen Wert in den Zieltyp.
        
        Args:
            value: Zu konvertierender Wert
            target_type: Zieltyp ('str', 'int', 'float', 'bool')
            
        Returns:
            Konvertierter Wert
        """
        if value is None:
            return None
            
        try:
            if target_type == "int":
                return int(float(value))
            elif target_type == "float":
                return float(value)
            elif target_type == "bool":
                return str(value).lower() in ("true", "1", "yes", "ja")
            else:
                return str(value)
        except (ValueError, TypeError):
            return None
    
    def _map_usage_type(self, usage: str) -> str:
        """Mapped einen Nutzungstyp auf CEA-Kategorien.
        
        Args:
            usage: Ursprünglicher Nutzungstyp
            
        Returns:
            CEA-Nutzungskategorie
        """
        usage = usage.lower()
        
        if any(x in usage for x in ["wohn", "mieth", "residential"]):
            return "RESIDENTIAL"
        elif any(x in usage for x in ["büro", "office"]):
            return "OFFICE"
        elif any(x in usage for x in ["handel", "retail", "geschäft"]):
            return "RETAIL"
        elif any(x in usage for x in ["industrie", "gewerbe"]):
            return "INDUSTRIAL"
        elif any(x in usage for x in ["bildung", "schule"]):
            return "EDUCATIONAL"
        elif any(x in usage for x in ["hotel", "beherbergung"]):
            return "HOTEL"
        else:
            return "MIXED"
    
    def validate_field(self, field_name: str, value: Any) -> Any:
        """Validiert einen Feldwert gegen die definierten Regeln.
        
        Args:
            field_name: Name des Felds
            value: Zu validierender Wert
            
        Returns:
            Validierter Wert
            
        Raises:
            ValueError: Wenn der Wert ungültig ist
        """
        if field_name not in self.validation_rules:
            return value
            
        rules = self.validation_rules[field_name]
        
        # Prüfe Minimum
        if "min" in rules and value < rules["min"]:
            raise ValueError(f"Wert {value} für {field_name} ist kleiner als Minimum {rules['min']}")
            
        # Prüfe Maximum
        if "max" in rules and value > rules["max"]:
            raise ValueError(f"Wert {value} für {field_name} ist größer als Maximum {rules['max']}")
            
        # Prüfe erlaubte Werte
        if "allowed_values" in rules and value not in rules["allowed_values"]:
            raise ValueError(f"Wert {value} für {field_name} ist nicht in erlaubten Werten {rules['allowed_values']}")
            
        return value

class CEABuildingProcessor(BuildingProcessorInterface, BaseProcessor):
    """CEA-spezifischer Gebäudeprozessor."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den CEA-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        BuildingProcessorInterface.__init__(self, config)
        BaseProcessor.__init__(self, config)
        
        # Lade CEA-Konfiguration
        self.cea_config = self._load_cea_config()
        
        # Initialisiere Mapping-Prozessor
        self.mapping_processor = MappingProcessor(config)
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Eingabedaten.
        
        Args:
            data: Eingabedaten mit CityGML-, WFS- und OSM-Daten
            
        Returns:
            Verarbeitete Daten
        """
        citygml_data = data.get('citygml', {})
        wfs_data = data.get('wfs', {})
        osm_data = data.get('osm', {})
        
        return self.process_buildings(citygml_data, wfs_data, osm_data)
        
    def _load_cea_config(self) -> Dict[str, Any]:
        """
        Lädt die CEA-Konfiguration.
        
        Returns:
            CEA-Konfiguration
        """
        try:
            cea_config_path = Path(self.config.get('cea', {}).get('config_file', 'config/cea/config.yml'))
            
            if not cea_config_path.exists():
                self.logger.error(f"❌ CEA-Konfiguration nicht gefunden: {cea_config_path}")
                return {}
                
            with open(cea_config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der CEA-Konfiguration: {str(e)}")
            return {}
            
    def process_buildings(self, citygml_data: Dict[str, Any], wfs_data: Dict[str, Any], osm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet Gebäudedaten für CEA.
        
        Args:
            citygml_data: CityGML-Gebäudedaten
            wfs_data: WFS-Gebäudedaten
            osm_data: OSM-Daten
            
        Returns:
            Verarbeitete Daten
        """
        try:
            # Validiere Eingabedaten
            if not self.validate_data(citygml_data):
                return {}
                
            # Verarbeite CityGML-Daten
            citygml_processed = self.mapping_processor.process(citygml_data, 'citygml')
            if not citygml_processed:
                return {}
                
            # Verarbeite WFS-Daten wenn vorhanden
            wfs_processed = {}
            if wfs_data:
                wfs_processed = self.mapping_processor.process(wfs_data, 'wfs')
                
            # Verarbeite OSM-Daten
            osm_buildings = osm_data.get('buildings', {})
            osm_streets = osm_data.get('streets', {})
            
            osm_buildings_processed = {}
            if osm_buildings:
                # Erstelle GeoDataFrame aus OSM-Gebäuden
                osm_buildings_gdf = gpd.GeoDataFrame.from_features(osm_buildings)
                # Hole zusätzliche Gebäude aus der Umgebung
                surrounding_buildings = fetch_osm_data(osm_buildings_gdf, data_type='buildings', config=self.config)
                # Kombiniere die Daten
                all_osm_buildings = pd.concat([osm_buildings_gdf, surrounding_buildings], ignore_index=True)
                osm_buildings_processed = self.mapping_processor.process({'features': all_osm_buildings}, 'osm')
                
            # Verarbeite OSM-Straßen
            osm_streets_processed = {}
            if osm_streets:
                # Erstelle GeoDataFrame aus OSM-Straßen
                osm_streets_gdf = gpd.GeoDataFrame.from_features(osm_streets)
                # Hole zusätzliche Straßen aus der Umgebung
                surrounding_streets = fetch_osm_data(osm_streets_gdf, data_type='streets', config=self.config)
                # Kombiniere die Daten
                all_osm_streets = pd.concat([osm_streets_gdf, surrounding_streets], ignore_index=True)
                osm_streets_processed = self.mapping_processor.process({'features': all_osm_streets}, 'osm')
            
            # Kombiniere alle Daten
            combined_data = self._combine_data(citygml_processed, wfs_processed, osm_buildings_processed, osm_streets_processed)
            if not combined_data:
                return {}
                
            # Wende CEA-spezifische Transformationen an
            cea_data = self._apply_cea_transformations(combined_data)
            if not cea_data:
                return {}
                
            return cea_data
            
        except Exception as e:
            self.handle_error(e, "cea_processing")
            return {}
            
    def _combine_data(self, citygml_data: Dict[str, Any], wfs_data: Dict[str, Any], osm_buildings_data: Dict[str, Any], osm_streets_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kombiniert Daten aus verschiedenen Quellen.
        
        Args:
            citygml_data: Verarbeitete CityGML-Daten
            wfs_data: Verarbeitete WFS-Daten
            osm_buildings_data: Verarbeitete OSM-Gebäudedaten
            osm_streets_data: Verarbeitete OSM-Straßendaten
            
        Returns:
            Kombinierte Daten
        """
        try:
            # Extrahiere Features
            citygml_features = citygml_data.get('features', pd.DataFrame())
            wfs_features = wfs_data.get('features', pd.DataFrame())
            osm_buildings_features = osm_buildings_data.get('features', pd.DataFrame())
            osm_streets_features = osm_streets_data.get('features', pd.DataFrame())
            
            # Kombiniere alle Features
            all_features = pd.concat([citygml_features, wfs_features, osm_buildings_features, osm_streets_features], ignore_index=True)
            
            # Entferne Duplikate basierend auf Geometrie
            all_features = all_features.drop_duplicates(subset=['geometry'])
            
            return {
                'features': all_features
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Kombinieren der Daten: {str(e)}")
            return {}
            
    def _apply_cea_transformations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wendet CEA-spezifische Transformationen an.
        
        Args:
            data: Zu transformierende Daten
            
        Returns:
            Transformierte Daten
        """
        try:
            features = data.get('features', pd.DataFrame())
            if features.empty:
                return {}
                
            # Hole CEA-Mappings aus der zentralen Mapping-Konfiguration
            cea_mappings = self.mapping_processor.mapping_config.get('cea_mappings', {})
            
            # Wende Bauperioden-Mapping an
            construction_periods = cea_mappings.get('construction_periods', {})
            features['construction_period'] = features['year_built'].apply(
                lambda year: next(
                    (period for period, [start, end] in construction_periods.items() 
                     if start <= year <= end),
                    'unknown'
                )
            )
            
            # Wende Gebäudetyp-Mapping an
            building_types = cea_mappings.get('building_types', {})
            features['cea_type'] = features['building_type'].map(
                {k: v['cea_type'] for k, v in building_types.items()}
            )
            features['construction'] = features['building_type'].map(
                {k: v['construction'] for k, v in building_types.items()}
            )
            features['window_wall_ratio'] = features['building_type'].map(
                {k: v['window_wall_ratio'] for k, v in building_types.items()}
            )
            features['occupancy'] = features['building_type'].map(
                {k: v['occupancy'] for k, v in building_types.items()}
            )
            
            # Fülle fehlende Werte mit Standardwerten
            geometry_defaults = self.cea_config.get('geometry', {}).get('defaults', {})
            features['height'] = features['height'].fillna(geometry_defaults.get('height', 10))
            features['floors'] = features['floors'].fillna(geometry_defaults.get('floors', 3))
            features['year_built'] = features['year_built'].fillna(geometry_defaults.get('year', 1990))
            
            return {
                'features': features
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei den CEA-Transformationen: {str(e)}")
            return {}

    def _map_construction_period(self, period: str) -> str:
        """Mappt eine Bauperiode auf einen CEA-Zeitcode.
        
        Args:
            period (str): Bauperiode aus WFS (z.B. "1848 - 1918")
            
        Returns:
            str: CEA-Zeitcode (z.B. "_A" oder "_B")
        """
        try:
            periods = self.mapping_processor.mapping_config.get('periods', {})
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
            periods = self.mapping_processor.mapping_config.get('periods', {})
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
            building_types = self.mapping_processor.mapping_config.get('building_types', {}).get('standard_prefix', {})
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
            required_fields = self.mapping_processor.metrics_config.get('required_fields', [])
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
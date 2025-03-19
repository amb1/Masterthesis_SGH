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

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from utils.config_loader import load_config
from utils.data_processing.base_building_processor import BuildingProcessorInterface
from utils.data_sources.fetch_osm_buildings import fetch_surrounding_buildings, process_osm_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_sources.fetch_wfs_data import ViennaWFS

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CEABuildingProcessor(BuildingProcessorInterface):
    """Konkrete Implementierung des BuildingProcessorInterface für CEA-Gebäudeverarbeitung"""
    
    def __init__(self, cea_config: dict, project_config: dict):
        """Initialisiert den CEA Building Processor.
        
        Args:
            cea_config (dict): CEA-spezifische Konfiguration
            project_config (dict): Projekt-Konfiguration
        """
        # Initialisiere die Basisklasse
        super().__init__()
        
        # Speichere Konfigurationen
        self.cea_config = cea_config
        self.project_config = project_config
        
        # Definiere absolute Pfade für Konfigurationsdateien
        self.metrics_path = root_dir / 'cfg' / 'cea' / 'building_metrics.yml'
        self.mapping_path = root_dir / 'cfg' / 'cea' / 'cea_mapping.yml'
        
        # Lade CEA-spezifische Konfigurationen
        try:
            # Lade Metrik-Konfiguration
            self.metrics_config = load_config(self.metrics_path) or {}
            if self.metrics_config:
                logger.info(f"✅ Metrik-Konfiguration geladen von {self.metrics_path}")
            else:
                logger.error(f"❌ Metrik-Konfiguration nicht gefunden: {self.metrics_path}")
            
            # Lade Mapping-Konfiguration
            self.mapping_config = load_config(self.mapping_path) or {}
            if self.mapping_config:
                logger.info(f"✅ Mapping-Konfiguration geladen von {self.mapping_path}")
            else:
                logger.error(f"❌ Mapping-Konfiguration nicht gefunden: {self.mapping_path}")
            
            logger.info("✅ CEA Building Processor initialisiert")
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Initialisierung: {str(e)}")
            raise
            
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
                
            # Hole Pfade aus der Konfiguration
            paths = self.project_config.get('paths', {})
            geometry_dir = project_dir / paths.get('inputs', {}).get('geometry', 'inputs/building-geometry')
            properties_dir = project_dir / paths.get('inputs', {}).get('properties', 'inputs/building-properties')
            networks_dir = project_dir / paths.get('inputs', {}).get('networks', 'inputs/networks')
            
            for directory in [geometry_dir, properties_dir, networks_dir]:
                directory.mkdir(parents=True, exist_ok=True)
                
            # 1. Speichere Site-Polygon
            site_path = geometry_dir / 'site.shp'
            site_gdf = gpd.GeoDataFrame(
                {'geometry': [self.site_polygon]}, 
                crs=self.project_config.get('crs', 'EPSG:31256')
            )
            site_gdf.to_file(site_path)
            logger.info(f"✅ Site-Polygon gespeichert: {site_path}")
            
            # 2. Hole WFS-Daten basierend auf site_polygon
            if hasattr(self, 'wfs') and self.wfs is not None:
                try:
                    # Berechne BBOX aus site_polygon mit Puffer
                    buffer_distance = self.project_config.get('processing', {}).get('surroundings', {}).get('buffer_distance', 100)
                    buffered_polygon = self.site_polygon.buffer(buffer_distance)
                    minx, miny, maxx, maxy = buffered_polygon.bounds
                    bbox = (minx, miny, maxx, maxy)
                    
                    # Hole WFS-Daten für alle Layer aus der Mapping-Konfiguration
                    self.wfs_data = {}
                    unique_wfs_layers = set()
                    
                    # Sammle alle benötigten WFS-Layer aus den Mappings
                    for mapping_type in ['zone_shp', 'typology_dbf']:
                        for mapping in self.mapping_config[mapping_type]['mappings'].values():
                            if 'wfs_layer' in mapping:
                                unique_wfs_layers.add(mapping['wfs_layer'])
                    
                    # Hole Daten für jeden Layer
                    for layer_name in unique_wfs_layers:
                        try:
                            layer_data = self.wfs.get_features(layer_name, bbox)
                            if layer_data is not None:
                                self.wfs_data[layer_name] = layer_data
                                logger.info(f"✅ WFS-Daten für Layer {layer_name} geladen: {len(layer_data)} Features")
                            else:
                                logger.warning(f"⚠️ Keine Daten für WFS-Layer {layer_name} gefunden")
                        except Exception as layer_error:
                            logger.error(f"❌ Fehler beim Laden von WFS-Layer {layer_name}: {str(layer_error)}")
                    
                    logger.info(f"✅ WFS-Daten für {len(self.wfs_data)} Layer geladen")
                except Exception as wfs_error:
                    logger.error(f"❌ Fehler beim Laden der WFS-Daten: {str(wfs_error)}")
                    self.wfs_data = {}
            
            # 3. Erstelle CEA-Dateien (zone.shp und typology.dbf)
            zone_gdf, typology_gdf = self._create_cea_files(geometry_dir, properties_dir)
            if zone_gdf is None or typology_gdf is None:
                return False, None
            
            # 4. Hole und speichere Umgebungsgebäude
            logger.info("🔄 Hole Umgebungsgebäude...")
            
            # Konfiguration für OSM-Gebäude
            surroundings_config = self.project_config.get('processing', {}).get('surroundings', {})
            building_defaults = self.project_config.get('building_defaults', {})
            
            osm_config = {
                'surroundings': {
                    'buffer_distance': surroundings_config.get('buffer_distance', 100),
                    'building_defaults': building_defaults
                }
            }
            
            surroundings_gdf = fetch_surrounding_buildings(site_gdf, osm_config)
            
            if surroundings_gdf is not None and not surroundings_gdf.empty:
                surroundings_gdf = process_osm_buildings(surroundings_gdf, building_defaults)
                surroundings_path = geometry_dir / 'surroundings.shp'
                surroundings_gdf.to_file(surroundings_path)
                logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gespeichert: {surroundings_path}")
            else:
                logger.warning("⚠️ Keine Umgebungsgebäude gefunden oder Fehler beim Abruf")
                surroundings_gdf = gpd.GeoDataFrame(geometry=[], crs=self.project_config.get('crs', 'EPSG:31256'))
            
            # 5. Hole und speichere Straßen
            logger.info("🔄 Hole Straßen...")
            street_tags = self.project_config.get('street_tags', [])
            streets_gdf = fetch_osm_streets(self.site_polygon, street_tags)
            
            if streets_gdf is not None:
                streets_path = networks_dir / 'streets.shp'
                streets_gdf.to_file(streets_path)
                logger.info(f"✅ {len(streets_gdf)} Straßen gespeichert: {streets_path}")
            
            # Erstelle Ausgabe-Dictionary
            output_data = {
                'zone': zone_gdf,
                'typology': typology_gdf,
                'surroundings': surroundings_gdf,
                'streets': streets_gdf,
                'site': site_gdf,
                'wfs_data': self.wfs_data if hasattr(self, 'wfs_data') else None
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
            periods = self.mapping_config.get('periods', {})
            if period in periods:
                categories = periods[period].get('categories', [])
                if categories:
                    return np.random.choice(categories)
            return "_A"  # Fallback wenn keine Zuordnung gefunden
        except Exception as e:
            logger.error(f"❌ Fehler beim Mapping der Bauperiode: {str(e)}")
            return "_A"

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
            return f"{cea_type}{cea_period}"
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen des STANDARD-Werts: {str(e)}")
            return "NONE_A"  # Fallback-Wert

    def _create_cea_files(self, geometry_dir: Path, properties_dir: Path) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Erstellt die CEA-Dateien (zone.shp und typology.shp).
        
        Args:
            geometry_dir (Path): Verzeichnis für Geometrie-Dateien
            properties_dir (Path): Verzeichnis für Eigenschafts-Dateien
            
        Returns:
            tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]: (zone_gdf, typology_gdf)
        """
        try:
            # Verfügbare Spalten loggen
            logger.info(f"Verfügbare Spalten in buildings_gdf: {list(self.buildings_gdf.columns)}")
            
            # 1. Erstelle zone.shp
            zone_gdf = self.buildings_gdf.copy()
            
            # Hole Standardwerte aus der Konfiguration
            defaults = self.mapping_config.get('defaults', {})
            field_mappings = self.mapping_config.get('field_mappings', {})
            
            # Berechne floors_ag basierend auf measured_height
            if 'floors_ag' in field_mappings:
                mapping = field_mappings['floors_ag']
                if mapping.get('source') in zone_gdf.columns:
                    source_col = mapping['source']
                    if mapping.get('calculation'):
                        # Führe die Berechnung durch
                        zone_gdf['floors_ag'] = eval(mapping['calculation'].replace('value', f'zone_gdf["{source_col}"]'))
                    else:
                        zone_gdf['floors_ag'] = zone_gdf[source_col]
                else:
                    zone_gdf['floors_ag'] = mapping.get('default', defaults.get('floors_ag', 4))
            
            # Setze floors_bg basierend auf NS-Feld
            if 'floors_bg' in field_mappings:
                mapping = field_mappings['floors_bg']
                if mapping.get('source') in zone_gdf.columns:
                    source_col = mapping['source']
                    mapping_dict = mapping.get('mapping', {})
                    zone_gdf['floors_bg'] = zone_gdf[source_col].map(lambda x: mapping_dict.get(x, mapping_dict.get('*', mapping.get('default', defaults.get('floors_bg', 1)))))
                else:
                    zone_gdf['floors_bg'] = mapping.get('default', defaults.get('floors_bg', 1))
            
            # Setze YEAR basierend auf L_BAUJ oder OBJ_STR2_TXT
            if 'year' in field_mappings:
                mapping = field_mappings['year']
                for source in mapping.get('sources', []):
                    if source['field'] in zone_gdf.columns:
                        if source['type'] == 'direct':
                            zone_gdf['YEAR'] = zone_gdf[source['field']].fillna(mapping.get('default', defaults.get('year', 1960)))
                        elif source['type'] == 'period_mapping':
                            zone_gdf['YEAR'] = zone_gdf[source['field']].apply(self._get_year_from_period)
                        break
                else:
                    zone_gdf['YEAR'] = mapping.get('default', defaults.get('year', 1960))
            
            # Setze USE-Typ basierend auf L_BAUTYP oder BAUTYP_TXT
            if 'use_type' in field_mappings:
                mapping = field_mappings['use_type']
                for source in mapping.get('sources', []):
                    if source['field'] in zone_gdf.columns:
                        zone_gdf['USE_TYPE'] = zone_gdf[source['field']].apply(self._map_building_type)
                        break
                else:
                    zone_gdf['USE_TYPE'] = mapping.get('default', defaults.get('use_type', "NONE"))
            
            # Setze STANDARD basierend auf USE_TYPE und Bauperiode
            if 'OBJ_STR2_TXT' in zone_gdf.columns:
                zone_gdf['STANDARD'] = zone_gdf.apply(
                    lambda row: self._create_standard_value(row['OBJ_STR2_TXT'], row['USE_TYPE']), 
                    axis=1
                )
            else:
                zone_gdf['STANDARD'] = zone_gdf['USE_TYPE'].apply(lambda x: f"{x}_A")
            
            # Setze Adressfelder
            for field, mapping in field_mappings.items():
                if field in ['postcode', 'house_no', 'street', 'resi_type']:
                    if mapping.get('source') in zone_gdf.columns:
                        zone_gdf[field] = zone_gdf[mapping['source']].fillna(mapping.get('default', defaults.get(field, '')))
                    else:
                        zone_gdf[field] = mapping.get('default', defaults.get(field, ''))
            
            # Füge WFS-Daten hinzu, wenn verfügbar
            if hasattr(self, 'wfs_data') and self.wfs_data:
                for layer_name, layer_data in self.wfs_data.items():
                    if layer_data is not None and not layer_data.empty:
                        try:
                            # Räumliche Verknüpfung
                            joined = gpd.sjoin_nearest(
                                zone_gdf,
                                layer_data,
                                how='left',
                                distance_col='distance'
                            )
                            
                            # Füge relevante Spalten hinzu
                            for col in layer_data.columns:
                                if col not in ['geometry', 'index', 'index_right']:
                                    zone_gdf[f"{layer_name}_{col}"] = joined[col]
                                    
                            logger.info(f"✅ WFS-Layer {layer_name} zu zone.shp hinzugefügt")
                        except Exception as e:
                            logger.warning(f"⚠️ Fehler beim Hinzufügen von Layer {layer_name}: {str(e)}")
            
            # Setze CRS
            zone_gdf.set_crs(self.config.get('crs', 'EPSG:31256'), inplace=True)
            
            # Speichere zone.shp
            zone_path = geometry_dir / 'zone.shp'
            zone_gdf.to_file(zone_path)
            logger.info(f"✅ Zone-Datei erstellt: {zone_path}")
            
            # 2. Erstelle typology.shp
            # Initialisiere Standardwerte
            default_year = 1990
            default_type = 'MFH'
            default_floors = 4
            default_height = 12
            
            # Erstelle typology_gdf mit Standardwerten und WFS-Daten wenn verfügbar
            typology_data = {
                'Name': zone_gdf.index,
                'YEAR': default_year,  # Standardwert
                'TYPE': default_type,  # Standardwert
                'STANDARD': f"{default_type}_A",  # Standardwert
                'FLOORS': default_floors,  # Standardwert
                'HEIGHT': default_height,  # Standardwert
                'geometry': zone_gdf.geometry
            }
            
            # Aktualisiere mit WFS-Daten wenn verfügbar
            if hasattr(self, 'wfs_data') and self.wfs_data:
                # YEAR aus GEBAEUDEINFOOGD
                if 'GEBAEUDEINFOOGD_BAUJAHR' in zone_gdf.columns:
                    typology_data['YEAR'] = zone_gdf['GEBAEUDEINFOOGD_BAUJAHR'].fillna(default_year)
                
                # TYPE und STANDARD aus GEBAEUDETYPOGD
                if 'GEBAEUDETYPOGD_OBJ_STR' in zone_gdf.columns:
                    building_types = zone_gdf['GEBAEUDETYPOGD_OBJ_STR'].fillna(default_type)
                    typology_data['TYPE'] = building_types
                    typology_data['STANDARD'] = building_types.apply(lambda x: f"{x}_A")
                
                # FLOORS aus GEBAEUDEINFOOGD
                if 'GEBAEUDEINFOOGD_GESCH_ANZ' in zone_gdf.columns:
                    typology_data['FLOORS'] = zone_gdf['GEBAEUDEINFOOGD_GESCH_ANZ'].fillna(default_floors)
                
                # HEIGHT aus FMZKBKMOGD oder measuredHeight
                if 'FMZKBKMOGD_O_KOTE' in zone_gdf.columns:
                    typology_data['HEIGHT'] = zone_gdf['FMZKBKMOGD_O_KOTE'].fillna(default_height)
                elif 'measuredHeight' in zone_gdf.columns:
                    typology_data['HEIGHT'] = zone_gdf['measuredHeight'].fillna(default_height)
            
            # Erstelle GeoDataFrame
            typology_gdf = gpd.GeoDataFrame(
                typology_data,
                crs=self.config.get('crs', 'EPSG:31256')
            )
            
            # Speichere typology.shp
            typology_path = properties_dir / 'typology.shp'
            typology_gdf.to_file(typology_path)
            logger.info(f"✅ Typologie-Datei erstellt: {typology_path}")
            
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
        """Verarbeitet ein einzelnes Gebäude."""
        try:
            # Kopiere Basisdaten
            processed_data = building_data.copy()
            
            # Setze CRS wenn nicht vorhanden
            if not hasattr(processed_data['geometry'], 'crs'):
                processed_data['geometry'].set_crs(epsg=31256, inplace=True)
            
            # Behandle MultiPolygon
            if processed_data['geometry'].geom_type == 'MultiPolygon':
                # Wähle den größten Polygon aus dem MultiPolygon
                polygons = list(processed_data['geometry'])
                areas = [p.area for p in polygons]
                largest_polygon = polygons[areas.index(max(areas))]
                processed_data['geometry'] = largest_polygon
                logger.info(f"MultiPolygon zu Polygon konvertiert (größte Fläche: {max(areas):.2f}m²)")
            
            # Füge Metadaten hinzu
            processed_data['data_source'] = 'CityGML'
            processed_data['processing_date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
            
            # Validiere und bereinige Geometrie
            if not processed_data['geometry'].is_valid:
                processed_data['geometry'] = processed_data['geometry'].buffer(0)
                if processed_data['geometry'].is_valid:
                    logger.info("Geometrie erfolgreich bereinigt")
                else:
                    logger.warning("⚠️ Geometrie konnte nicht bereinigt werden")
                
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
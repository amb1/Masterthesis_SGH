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
from utils.data_sources.fetch_wfs_data import ViennaWFS

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CEABuildingProcessor(BuildingProcessorInterface):
    """Konkrete Implementierung des BuildingProcessorInterface für CEA-Gebäudeverarbeitung"""
    
    def __init__(self, config: Dict[str, Any], project_config: Dict[str, Any]):
        """Initialisiert den CEA Building Processor.
        
        Args:
            config (Dict[str, Any]): CEA-Konfiguration
            project_config (Dict[str, Any]): Projekt-Konfiguration
        """
        # Kombiniere die Konfigurationen
        combined_config = {
            'cea': config,
            'project': project_config,
            'wfs': config.get('wfs', {}),
            'osm': {
                'surroundings': {
                    'buffer_distance': 100,  # Meter
                    'building_types': ['residential', 'commercial', 'industrial', 'school', 'university', 'hospital'],
                    'building_defaults': {
                        'height': 10,  # Standardhöhe in Metern
                        'floors': 3,   # Standardanzahl der Stockwerke
                        'year': 1990   # Standardbaujahr
                    },
                    'street_tags': config.get('osm', {}).get('street_tags', [])
                },
                'street_tags': config.get('osm', {}).get('street_tags', [])
            },
            'crs': config.get('crs', 'EPSG:31256')
        }
        
        # Initialisiere die Basisklasse
        super().__init__(combined_config)
        
        # Definiere absolute Pfade für Konfigurationsdateien
        self.base_path = Path(__file__).resolve().parent.parent.parent
        self.metrics_path = self.base_path / 'cfg' / 'cea' / 'building_metrics.yml'
        self.mapping_path = self.base_path / 'cfg' / 'cea' / 'cea_mapping.yml'
        
        # Lade CEA-spezifische Konfigurationen
        try:
            # Lade Metrik-Konfiguration
            if self.metrics_path.exists():
                with open(self.metrics_path, 'r', encoding='utf-8') as f:
                    self.metrics_config = yaml.safe_load(f)
                logger.info(f"✅ Metrik-Konfiguration geladen von {self.metrics_path}")
            else:
                logger.error(f"❌ Metrik-Konfiguration nicht gefunden: {self.metrics_path}")
                self.metrics_config = {}
            
            # Lade Mapping-Konfiguration
            if self.mapping_path.exists():
                with open(self.mapping_path, 'r', encoding='utf-8') as f:
                    self.mapping_config = yaml.safe_load(f)
                logger.info(f"✅ Mapping-Konfiguration geladen von {self.mapping_path}")
            else:
                logger.error(f"❌ Mapping-Konfiguration nicht gefunden: {self.mapping_path}")
                self.mapping_config = {}
            
            # Initialisiere WFS-Client
            if 'wfs' in config:
                self.wfs = ViennaWFS(config['wfs'])
                logger.info("✅ WFS initialisiert")
            else:
                self.wfs = None
                logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            
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
            
            # 2. Hole WFS-Daten basierend auf site_polygon
            if self.wfs is not None:
                try:
                    # Berechne BBOX aus site_polygon
                    minx, miny, maxx, maxy = self.site_polygon.bounds
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
            
            # Erstelle GeoDataFrame aus site_polygon mit CRS
            site_gdf = gpd.GeoDataFrame({'geometry': [self.site_polygon]}, crs=self.config.get('crs', 'EPSG:31256'))
            
            surroundings_gdf = fetch_surrounding_buildings(
                site_gdf.geometry[0],  # Verwende das erste (und einzige) Polygon
                self.config.get('osm', {})
            )
            
            if surroundings_gdf is not None:
                # Setze CRS für surroundings_gdf
                surroundings_gdf.set_crs(self.config.get('crs', 'EPSG:31256'), inplace=True)
                
                surroundings_gdf = process_osm_buildings(
                    surroundings_gdf,
                    self.config.get('osm', {}).get('building_defaults', {})
                )
                surroundings_path = geometry_dir / 'surroundings.shp'
                surroundings_gdf.to_file(surroundings_path)
                logger.info(f"✅ {len(surroundings_gdf)} Umgebungsgebäude gespeichert: {surroundings_path}")
            
            # 5. Hole und speichere Straßen
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
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, Tuple
import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import Polygon, Point, MultiPolygon
import numpy as np
import os
import sys
from core.config_manager import load_config

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from pipeline.geometry.site_polygon_utils import create_site_polygon, save_site_polygon
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings
from pipeline.data_sources.wfs_fetcher import ViennaWFS

logger = logging.getLogger(__name__)

def load_project_config():
    """Lädt die Projekt-Konfiguration"""
    try:
        # Lade zuerst die Projekt-Konfiguration
        root_dir = Path(__file__).resolve().parent.parent.parent
        project_config_path = root_dir / 'config' / 'project.yml'
        logger.info(f"📂 Lade Projekt-Konfiguration: {project_config_path}")
        
        # Lade die Konfiguration direkt
        config = load_config(str(project_config_path))
        if not config:
            logger.error("❌ Projekt-Konfiguration konnte nicht geladen werden")
            return None
            
        logger.info("✅ Projekt-Konfiguration erfolgreich geladen")
        return config

    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        return None

class BaseProcessor(ABC):
    """Basisklasse für alle Prozessoren."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Basis-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Eingabedaten.
        
        Args:
            data: Eingabedaten
            
        Returns:
            Verarbeitete Daten
        """
        pass
        
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        Validiert die Eingabedaten.
        
        Args:
            data: Zu validierende Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            if not data:
                self.logger.warning("⚠️ Keine Daten vorhanden")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Datenvalidierung: {str(e)}")
            return False
            
    def validate_geometry(self, gdf: gpd.GeoDataFrame) -> bool:
        """
        Validiert die Geometrie eines GeoDataFrames.
        
        Args:
            gdf: Zu validierender GeoDataFrame
            
        Returns:
            True wenn Geometrie valide
        """
        try:
            if gdf is None or gdf.empty:
                self.logger.warning("⚠️ Leerer GeoDataFrame")
                return False
                
            if 'geometry' not in gdf.columns:
                self.logger.warning("⚠️ Keine Geometriespalte vorhanden")
                return False
                
            invalid_geoms = gdf[~gdf.geometry.is_valid]
            if not invalid_geoms.empty:
                self.logger.warning(f"⚠️ {len(invalid_geoms)} ungültige Geometrien gefunden")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return False
            
    def validate_attributes(self, data: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Validiert die Attribute der Daten.
        
        Args:
            data: Zu validierende Daten
            required_fields: Liste der Pflichtfelder
            
        Returns:
            True wenn Attribute valide
        """
        try:
            if not data:
                self.logger.warning("⚠️ Keine Daten vorhanden")
                return False
                
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                self.logger.warning(f"⚠️ Fehlende Pflichtfelder: {missing_fields}")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Attributvalidierung: {str(e)}")
            return False
            
    def log_processing_stats(self, input_data: Dict[str, Any], output_data: Dict[str, Any]):
        """
        Protokolliert Statistiken zur Datenverarbeitung.
        
        Args:
            input_data: Eingabedaten
            output_data: Ausgabedaten
        """
        try:
            input_count = len(input_data) if input_data else 0
            output_count = len(output_data) if output_data else 0
            
            self.logger.info(f"📊 Verarbeitungsstatistik:")
            self.logger.info(f"   - Eingabedatensätze: {input_count}")
            self.logger.info(f"   - Ausgabedatensätze: {output_count}")
            
            if input_count > output_count:
                self.logger.warning(f"⚠️ {input_count - output_count} Datensätze wurden gefiltert")
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Protokollieren der Statistik: {str(e)}")
            
    def handle_error(self, error: Exception, step: str):
        """
        Behandelt einen aufgetretenen Fehler.
        
        Args:
            error: Aufgetretener Fehler
            step: Verarbeitungsschritt
        """
        self.logger.error(f"❌ Fehler in Schritt '{step}': {str(error)}")
        if hasattr(error, '__traceback__'):
            self.logger.debug(f"Traceback:", exc_info=error)

class BuildingProcessorInterface(ABC):
    """Interface für Gebäudeprozessoren"""
    
    def __init__(self, config=None):
        """Initialisiert den Building Processor."""
        self.buildings_gdf = None
        self.site_polygon = None
        
        # Lade Konfigurationen
        if config:
            self.project_config = config
        else:
            self.project_config = load_config('config/global.yml')
            
        if not self.project_config:
            raise ValueError("❌ Keine gültige Projekt-Konfiguration gefunden")
            
        logger.info("✅ Projekt-Konfiguration geladen")
        
        # Hole spezifische Konfigurationen
        self.paths = self.project_config.get('project', {}).get('paths', {})
        
        # Logger Setup
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        
        # Stelle sicher, dass ein Handler existiert
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
            
        # Initialisiere Datenspeicher
        self.building_parts_gdf = None
        self.wfs_data = {}
        
        # Initialisiere WFS mit der Konfiguration
        if self.project_config.get('wfs'):
            self.wfs = ViennaWFS(config=self.project_config['wfs'])
            self.logger.info("✅ WFS initialisiert")
        else:
            self.logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            
    def _load_specific_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """Lädt eine spezifische Konfigurationsdatei.
        
        Args:
            config_type: Art der Konfiguration ('wfs', 'osm', 'cea')
            
        Returns:
            Optional[Dict[str, Any]]: Geladene Konfiguration oder None bei Fehler
        """
        try:
            # Hole Pfad aus project_config
            config_path = self.project_config.get(config_type, {}).get('config')
            if not config_path:
                self.logger.warning(f"⚠️ Kein Konfigurationspfad für {config_type} gefunden")
                return None
                
            # Konstruiere absoluten Pfad
            root_dir = Path(__file__).resolve().parent.parent.parent
            config_path = root_dir / 'config' / config_path
            
            if not config_path.exists():
                self.logger.error(f"❌ Konfigurationsdatei nicht gefunden: {config_path}")
                return None
                
            return self.load_config(config_path)
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der {config_type}-Konfiguration: {str(e)}")
            return None
            
    def load_config(self, config_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
        """Lädt eine Konfigurationsdatei
        
        Args:
            config_path: Pfad zur Konfigurationsdatei (String oder Path-Objekt)
            
        Returns:
            Optional[Dict[str, Any]]: Geladene Konfiguration oder None bei Fehler
        """
        try:
            # Konvertiere config_path zu Path-Objekt für Existenzprüfung
            path = Path(config_path)
            if not path.exists():
                self.logger.error(f"❌ Konfigurationsdatei nicht gefunden: {path}")
                return None
                
            # Lade die Konfiguration
            config = load_config(str(path))
            if not config:
                self.logger.error(f"❌ Konfiguration konnte nicht geladen werden: {path}")
                return None
            
            # Validiere, dass config ein Dictionary ist
            if not isinstance(config, dict):
                self.logger.error(f"❌ Ungültiges Konfigurationsformat: {type(config)}")
                return None
                
            self.logger.info(f"✅ Konfiguration geladen: {path.name}")
            return config
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Konfiguration {config_path}: {str(e)}")
            return None
            
    def process_citygml(self, citygml_file: str) -> bool:
        """Verarbeitet eine CityGML-Datei und extrahiert Gebäudedaten.

        Args:
            citygml_file: Pfad zur CityGML-Datei
        """
        try:
            self.logger.info(f"📂 Verarbeite CityGML-Datei: {citygml_file}")

            # Hole Output-Pfad aus der Konfiguration
            output_dir = Path(self.paths['outputs']['buildings'])
            output_dir.mkdir(parents=True, exist_ok=True)

            # Extrahiere Gebäude und Gebäudeteile
            buildings_gdf = fetch_citygml_buildings(citygml_file, output_dir)
            if buildings_gdf is None or buildings_gdf.empty:
                self.logger.error("❌ Keine Gebäude gefunden")
                return False

            # Speichere Gebäude-GeoDataFrame
            self.buildings_gdf = buildings_gdf

            # Zähle Gebäude und Gebäudeteile
            building_count = len(buildings_gdf[~buildings_gdf['is_building_part']])
            building_parts_count = len(buildings_gdf[buildings_gdf['is_building_part']])
            self.logger.info(f"✅ {building_count} Gebäude extrahiert ({building_parts_count} Gebäudeteile gefunden)")

            # Erstelle Site-Polygon
            buffer_distance = self.project_config.get('processing', {}).get('site_polygon', {}).get('buffer_distance', 3)
            self.site_polygon = create_site_polygon(self.buildings_gdf, buffer_distance)
            self.logger.info("✅ Site-Polygon erstellt")

            # Hole WFS-Daten wenn WFS verfügbar
            if hasattr(self, 'wfs'):
                self.logger.info("🔍 WFS-Konfiguration:")
                streams = self.project_config['wfs'].get('streams', [])
                self.logger.info(f"Gefundene Streams: {len(streams)}")

                if not streams:
                    self.logger.warning("⚠️ Keine WFS-Streams konfiguriert")
                    return False

                # Konvertiere Site-Polygon zu BBOX
                bounds = self.site_polygon.bounds
                # Konvertiere zu ganzzahligen Koordinaten und erweitere den Bereich
                bbox = (
                    int(bounds[0]) - 100,  # min_x mit Puffer
                    int(bounds[1]) - 100,  # min_y mit Puffer
                    int(bounds[2]) + 100,  # max_x mit Puffer
                    int(bounds[3]) + 100   # max_y mit Puffer
                )
                self.logger.info(f"📍 BBOX für WFS-Anfragen: {bbox}")
                
                # Verarbeite Streams
                wfs_data = self.wfs.process_streams(bbox)
                if not wfs_data:
                    self.logger.warning("⚠️ Keine WFS-Daten verfügbar")
                    return False

            # Speichere Ergebnisse
            # Speichere Gebäude als GeoJSON
            output_path = output_dir / 'buildings.geojson'
            self.buildings_gdf.to_file(output_path, driver='GeoJSON')
            self.logger.info(f"✅ Gebäude gespeichert nach {output_path}")
            
            # Speichere Site-Polygon als Shapefile
            site_path = output_dir / 'site.shp'
            if isinstance(self.site_polygon, (str, dict)):
                self.logger.warning("⚠️ Site-Polygon hat ungültigen Geometrietyp, versuche Konvertierung")
                if isinstance(self.site_polygon, dict) and 'geometry' in self.site_polygon:
                    self.site_polygon = self.site_polygon['geometry']
            site_gdf = gpd.GeoDataFrame({'geometry': [self.site_polygon]}, crs=self.project_config.get('crs', 'EPSG:31256'))
            site_gdf.to_file(site_path)
            self.logger.info(f"✅ Site-Polygon gespeichert nach {site_path}")
            
            return True

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
            return False
            
    def _validate_and_repair_geometries(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Validiert und repariert Geometrien im GeoDataFrame.
        
        Args:
            gdf (gpd.GeoDataFrame): GeoDataFrame mit Geometrien
            
        Returns:
            gpd.GeoDataFrame: GeoDataFrame mit reparierten Geometrien
        """
        try:
            # Kopiere DataFrame
            result_gdf = gdf.copy()
            
            # Validiere und repariere jede Geometrie
            for idx, row in result_gdf.iterrows():
                geom = row.geometry
                
                # Prüfe ob Geometrie gültig ist
                if not geom.is_valid:
                    self.logger.warning(f"⚠️ Ungültige Geometrie gefunden für {row.get('gml_id', idx)}")
                    
                    # Versuche Geometrie zu reparieren
                    repaired_geom = geom.buffer(0)
                    
                    # Prüfe ob Reparatur erfolgreich war
                    if repaired_geom.is_valid:
                        result_gdf.at[idx, 'geometry'] = repaired_geom
                        self.logger.info(f"✅ Geometrie repariert für {row.get('gml_id', idx)}")
            else:
                        self.logger.error(f"❌ Geometrie konnte nicht repariert werden für {row.get('gml_id', idx)}")
                        
            return result_gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return gdf
            
    def _process_building_parts(self):
        """Verarbeitet BuildingParts und fügt sie zu ihren Hauptgebäuden hinzu."""
        try:
            if self.building_parts_gdf is None or self.building_parts_gdf.empty:
                return
                
            # Gruppiere BuildingParts nach Parent-ID
            grouped_parts = self.building_parts_gdf.groupby('parent_id')
            
            # Verarbeite jede Gruppe
            for parent_id, parts in grouped_parts:
                if parent_id in self.buildings_gdf.index:
                    # Hole Hauptgebäude
                    main_building = self.buildings_gdf.loc[parent_id]
                    
                    # Kombiniere Geometrien
                    all_geometries = [main_building.geometry] + list(parts.geometry)
                    combined_geom = MultiPolygon(all_geometries)
                    
                    # Aktualisiere Hauptgebäude
                    self.buildings_gdf.at[parent_id, 'geometry'] = combined_geom
                    self.buildings_gdf.at[parent_id, 'has_building_parts'] = True
                    self.buildings_gdf.at[parent_id, 'building_parts_count'] = len(parts)
                    
                    # Übernehme zusätzliche Attribute von BuildingParts
                    for attr in parts.columns:
                        if attr not in ['geometry', 'gml_id', 'parent_id', 'type']:
                            values = parts[attr].dropna()
                            if not values.empty:
                                self.buildings_gdf.at[parent_id, f'part_{attr}'] = values.iloc[0]
                                
            self.logger.info(f"✅ {len(grouped_parts)} BuildingParts verarbeitet")

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der BuildingPart-Verarbeitung: {str(e)}")
    
    @abstractmethod
    def process_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein einzelnes Gebäude.
        
        Args:
            building_data (dict): Die Gebäudeinformationen
            
        Returns:
            dict: Die verarbeiteten Gebäudeinformationen
        """
        pass
        
    @abstractmethod
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Validiert Gebäudedaten.
        
        Args:
            building_data (dict): Die zu validierenden Gebäudeinformationen
            
        Returns:
            bool: True wenn die Daten gültig sind
        """
        pass
    
    def save_buildings(self, output_dir: str = "local/data/outputs/buildings") -> None:
        """Speichert die verarbeiteten Gebäudedaten.
        
        Args:
            output_dir (str): Verzeichnis für die Ausgabedateien
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            if self.buildings_gdf is not None:
                # Speichere Gebäude als GeoJSON
                buildings_path = os.path.join(output_dir, "buildings.geojson")
                self.buildings_gdf.to_file(buildings_path, driver="GeoJSON")
                self.logger.info(f"✅ Gebäude gespeichert nach {buildings_path}")
                
            if self.building_parts_gdf is not None:
                # Speichere Gebäudeteile als GeoJSON
                parts_path = os.path.join(output_dir, "building_parts.geojson")
                self.building_parts_gdf.to_file(parts_path, driver="GeoJSON")
                self.logger.info(f"✅ Gebäudeteile gespeichert nach {parts_path}")
                
            if self.site_polygon is not None:
                # Speichere Site-Polygon als Shapefile für CEA
                site_path = os.path.join(output_dir, "site.shp")
                
                # Stelle sicher, dass die Geometrie ein Polygon ist
                if not isinstance(self.site_polygon, (Polygon, MultiPolygon)):
                    self.logger.warning("⚠️ Site-Polygon hat ungültigen Geometrietyp, versuche Konvertierung")
                    try:
                        # Versuche verschiedene Konvertierungsmethoden
                        if hasattr(self.site_polygon, '__geo_interface__'):
                            geom = self.site_polygon.__geo_interface__
                            if geom['type'].lower() == 'featurecollection':
                                # Nehme das erste Feature
                                feature = geom['features'][0]
                                site_polygon = Polygon(feature['geometry']['coordinates'][0])
                            else:
                                site_polygon = Polygon(geom['coordinates'][0])
                        else:
                            site_polygon = Polygon(self.site_polygon.exterior.coords)
                    except Exception as e:
                        self.logger.error(f"❌ Fehler bei der Geometrie-Konvertierung: {str(e)}")
                        return
                else:
                    site_polygon = self.site_polygon
                
                # Erstelle GeoDataFrame und speichere
                site_gdf = gpd.GeoDataFrame(
                    {'geometry': [site_polygon]}, 
                    crs=self.project_config.get('crs', 'EPSG:31256')
                )
                site_gdf.to_file(site_path)
                self.logger.info(f"✅ Site-Polygon gespeichert nach {site_path}")

        except Exception as e:
            self.logger.error(f"❌ Fehler beim Speichern der Daten: {str(e)}")
            raise

class BasicBuildingProcessor(BuildingProcessorInterface):
    """Einfache Implementierung des BuildingProcessorInterface"""
    
    def process_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Minimale Implementierung der Gebäudeverarbeitung."""
        return building_data
        
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Minimale Implementierung der Gebäudevalidierung."""
        return True if building_data.get('geometry') is not None else False

def create_site_polygon(buildings_gdf: gpd.GeoDataFrame) -> Polygon:
    """Erstellt ein Site-Polygon aus den Gebäudegeometrien.
    
    Args:
        buildings_gdf (gpd.GeoDataFrame): GeoDataFrame mit Gebäudegeometrien
        
    Returns:
        Polygon: Site-Polygon
    """
    try:
        # Erstelle äußere Hülle um alle Gebäude
        logging.info("📐 Erstelle äußere Hülle um alle Gebäude")
        all_geometries = buildings_gdf.geometry.unary_union
        
        # Erstelle convex hull und dann Buffer
        logging.info("🔲 Erstelle Buffer mit Abstand 5m")
        convex_hull = all_geometries.convex_hull
        site_polygon = convex_hull.buffer(5)
        
        # Berechne Fläche und Umfang
        area = site_polygon.area
        perimeter = site_polygon.length
        
        logging.info(f"✅ Standortpolygon erstellt:\n- Fläche: {area:.2f} m²\n- Umfang: {perimeter:.2f} m")
        
        return site_polygon
        
    except Exception as e:
        logging.error(f"❌ Fehler beim Erstellen des Site-Polygons: {str(e)}")
        return None

def main():
    """Hauptfunktion zum Ausführen des Base Building Processors."""
    try:
        logger.info("🔎 Base Building Processor Test-Modus")
        
        # Lade Projekt-Konfiguration - Korrigierter Pfad
        root_dir = Path(__file__).resolve().parent.parent.parent
        config_path = root_dir / "config" / "project.yml"
        logger.info(f"📂 Lade Projekt-Konfiguration: {config_path}")
        
        # Lade die Konfiguration direkt mit load_config
        config = load_config(config_path)
        if not config:
            logger.error("❌ Keine gültige Konfiguration gefunden")
            return
            
        # Validiere, dass config ein Dictionary ist
        if not isinstance(config, dict):
            logger.error(f"❌ Ungültiges Konfigurationsformat: {type(config)}")
            return
            
        # Lade WFS-Konfiguration
        wfs_config = config.get('data_source', {}).get('wfs', {})
        if not wfs_config:
            logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            return
            
        # Lade CityGML-Konfiguration
        citygml_config = config.get('data_source', {}).get('citygml', {})
        if not citygml_config:
            logger.error("❌ Keine CityGML-Konfiguration gefunden")
            return
            
        # Konstruiere absoluten Pfad zur CityGML-Datei
        citygml_base_path = Path(citygml_config.get('base_path', ''))
        if citygml_base_path.parts[0] == 'local':
            citygml_base_path = citygml_base_path.relative_to('local')
        citygml_path = root_dir / citygml_base_path / citygml_config.get('default_file', '')
        
        if not citygml_path.exists():
            logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            return
            
        # Hole Ausgabepfade aus der Konfiguration
        output_dir = Path(config['project']['paths']['outputs']['citygml'])
        if output_dir.parts[0] == 'local':
            output_dir = output_dir.relative_to('local')
        output_dir = root_dir / output_dir
        
        # Erstelle Ausgabeverzeichnis falls nicht vorhanden
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Führe die Verarbeitung durch
        buildings_gdf = fetch_citygml_buildings(str(citygml_path), str(output_dir), config)
        
        if buildings_gdf is not None:
            logger.info(f"✅ {len(buildings_gdf)} Gebäude extrahiert")
        else:
            logger.error("❌ Fehler beim Extrahieren der Gebäude")
            
    except Exception as e:
        logger.error(f"❌ Fehler im Hauptprogramm: {str(e)}")

if __name__ == "__main__":
    main() 
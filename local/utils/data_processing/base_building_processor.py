from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union, Tuple
import logging
import geopandas as gpd
import pandas as pd
from pathlib import Path
from shapely.geometry import Polygon, Point, MultiPolygon
import numpy as np
import os
import yaml
import sys

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(root_dir))

from utils.data_processing.create_site_polygon import create_site_polygon, save_site_polygon
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings
from utils.data_sources.fetch_wfs_data import ViennaWFS

class BuildingProcessorInterface(ABC):
    """Interface für Gebäudeprozessoren"""
    
    def __init__(self, config_path: str = "local/cfg/project_config.yml"):
        """Initialisiert den Building Processor.
        
        Args:
            config_path (str): Pfad zur Konfigurationsdatei
        """
        # Speichere Konfigurationspfad
        self.config_path = config_path
        
        # Lade Konfiguration
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        
        # Stelle sicher, dass ein Handler existiert
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
            
        # Initialisiere Datenspeicher
        self.buildings_gdf = None
        self.building_parts_gdf = None
        self.site_polygon = None
        self.wfs_data = {}
        
        # Lade WFS-Konfiguration
        wfs_config_path = str(Path(config_path).parent / "wfs" / "wfs_config.yml")
        self.logger.info(f"🔍 Suche WFS-Konfiguration unter: {wfs_config_path}")
        
        if os.path.exists(wfs_config_path):
            self.logger.info(f"✅ WFS-Konfiguration gefunden unter: {wfs_config_path}")
            with open(wfs_config_path, 'r', encoding='utf-8') as f:
                wfs_config = yaml.safe_load(f).get('vienna_wfs', {})
                
            # Füge die WFS-Konfiguration zum Hauptconfig hinzu
            self.config['vienna_wfs'] = wfs_config
            self.logger.info("✅ WFS-Konfiguration geladen")
            
            # Initialisiere WFS mit der geladenen Konfiguration
            self.wfs = ViennaWFS(config=wfs_config)
            
        else:
            self.logger.warning(f"⚠️ WFS-Konfiguration nicht gefunden unter {wfs_config_path}")
            
        logging.info("✅ Base Building Processor initialisiert")
        
    def process_citygml(self, citygml_file: str) -> None:
        """Verarbeitet eine CityGML-Datei und extrahiert Gebäudedaten.

        Args:
            citygml_file: Pfad zur CityGML-Datei
        """
        try:
            self.logger.info(f"📂 Verarbeite CityGML-Datei: {citygml_file}")

            # Erstelle Output-Verzeichnis
            output_dir = os.path.join(os.path.dirname(citygml_file), '..', 'outputs', 'buildings')
            os.makedirs(output_dir, exist_ok=True)

            # Extrahiere Gebäude und Gebäudeteile
            buildings_gdf = fetch_citygml_buildings(citygml_file, output_dir)
            if buildings_gdf is None or buildings_gdf.empty:
                self.logger.error("❌ Keine Gebäude gefunden")
                return

            # Speichere Gebäude-GeoDataFrame
            self.buildings_gdf = buildings_gdf

            # Zähle Gebäude und Gebäudeteile
            building_count = len(buildings_gdf[~buildings_gdf['is_building_part']])
            building_parts_count = len(buildings_gdf[buildings_gdf['is_building_part']])
            self.logger.info(f"✅ {building_count} Gebäude extrahiert ({building_parts_count} Gebäudeteile gefunden)")

            # Erstelle Site-Polygon
            self.site_polygon = create_site_polygon(self.buildings_gdf)
            self.logger.info("✅ Site-Polygon erstellt")

            # Hole WFS-Daten wenn WFS verfügbar
            if hasattr(self, 'wfs'):
                self.logger.info("🔍 WFS-Konfiguration:")
                streams = self.config['vienna_wfs'].get('streams', [])
                self.logger.info(f"Gefundene Streams: {len(streams)}")

                if not streams:
                    self.logger.warning("⚠️ Keine WFS-Streams konfiguriert")
                    return

                # Konvertiere Site-Polygon zu BBOX
                bounds = self.site_polygon.total_bounds
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
                    return

            # Speichere Ergebnisse
            self.save_buildings(output_dir)

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
            raise
            
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
                    crs=self.config.get('crs', 'EPSG:31256')
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("🔎 Base Building Processor Test-Modus")
    
    try:
        # Initialisiere Processor
        processor = BasicBuildingProcessor()
        
        # Teste CityGML-Verarbeitung
        citygml_path = "local/data/inputs/citygml/099082.gml"
        if os.path.exists(citygml_path):
            processor.process_citygml(citygml_path)
            
            # Speichere Ergebnisse
            output_dir = "local/data/outputs/buildings"
            processor.save_buildings(output_dir)
            logging.info("✅ Test erfolgreich abgeschlossen")
        else:
            logging.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            
    except Exception as e:
        logging.error(f"❌ Fehler im Test-Modus: {str(e)}") 
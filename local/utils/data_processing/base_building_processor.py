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
        
        # Initialisiere WFS
        self.wfs = ViennaWFS()
        
        logging.info("✅ Base Building Processor initialisiert")
        
    def process_citygml(self, citygml_path: str) -> None:
        """Verarbeitet die CityGML-Datei und extrahiert Gebäude und Gebäudeteile."""
        try:
            self.logger.info(f"📂 Verarbeite CityGML-Datei: {citygml_path}")
            
            buildings_gdf = fetch_citygml_buildings(citygml_path, self.config)
            
            # Trenne Gebäude und Gebäudeteile
            self.buildings_gdf = buildings_gdf[buildings_gdf['building_part'] == False].copy()
            self.building_parts_gdf = buildings_gdf[buildings_gdf['building_part'] == True].copy()
            
            self.logger.info(f"✅ {len(self.buildings_gdf)} Gebäude und {len(self.building_parts_gdf)} Gebäudeteile extrahiert")
            
            # Validiere und repariere Geometrien
            self.buildings_gdf = self._validate_and_repair_geometries(self.buildings_gdf)
            self.building_parts_gdf = self._validate_and_repair_geometries(self.building_parts_gdf)
            
            # Verarbeite BuildingParts
            self._process_building_parts()
            
            # Erstelle Site-Polygon
            self.site_polygon = create_site_polygon(self.buildings_gdf)
            if self.site_polygon is None:
                self.logger.error("❌ Fehler beim Erstellen des Site-Polygons")
                return
                
            self.logger.info("✅ Site-Polygon erstellt")
            
            # Hole WFS-Daten basierend auf Site-Polygon
            bbox = self.site_polygon.bounds
            self.wfs_data = self.wfs.fetch_data({'streams': self.config.get('vienna_wfs', {}).get('streams', [])}, bbox=bbox)
            
            if not self.wfs_data:
                self.logger.warning("⚠️ Keine WFS-Daten verfügbar")
            else:
                self.logger.info(f"✅ WFS-Daten für {len(self.wfs_data)} Layer geladen")
                
            # Reichere Gebäudedaten mit WFS-Daten an
            if self.wfs_data:
                self.buildings_gdf = self.wfs.enrich_with_wfs(self.buildings_gdf, bbox=bbox)
            
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
    
    def save_buildings(self, output_dir: str) -> None:
        """Speichert die verarbeiteten Gebäudedaten."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            if self.buildings_gdf is not None:
                buildings_path = os.path.join(output_dir, "buildings.geojson")
                self.buildings_gdf.to_file(buildings_path, driver="GeoJSON")
                self.logger.info(f"✅ Gebäude gespeichert nach {buildings_path}")
                
            if self.building_parts_gdf is not None:
                parts_path = os.path.join(output_dir, "building_parts.geojson")
                self.building_parts_gdf.to_file(parts_path, driver="GeoJSON")
                self.logger.info(f"✅ Gebäudeteile gespeichert nach {parts_path}")
                
            if self.site_polygon is not None:
                site_path = os.path.join(output_dir, "site_polygon.geojson")
                save_site_polygon(self.site_polygon, site_path)
                self.logger.info(f"✅ Site Polygon gespeichert nach {site_path}")
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Speichern der Daten: {str(e)}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info("🔎 Base Building Processor Test-Modus")
    
    try:
        # Initialisiere Processor
        processor = BuildingProcessorInterface()
        
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
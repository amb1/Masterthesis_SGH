from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import geopandas as gpd
from pathlib import Path

class BuildingProcessorInterface(ABC):
    """Interface für Gebäudeprozessoren"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den Building Processor.
        
        Args:
            config (dict): Die Konfiguration
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        
        # Stelle sicher, dass ein Handler existiert
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
    
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
    
    @abstractmethod
    def enrich_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reichert Gebäudedaten an.
        
        Args:
            building_data (dict): Die anzureichernden Gebäudeinformationen
            
        Returns:
            dict: Die angereicherten Gebäudeinformationen
        """
        pass
    
    def save_buildings(self, buildings_gdf: gpd.GeoDataFrame, output_path: Path) -> bool:
        """Speichert Gebäude als Shapefile.
        
        Args:
            buildings_gdf (gpd.GeoDataFrame): Die zu speichernden Gebäude
            output_path (Path): Der Ausgabepfad
            
        Returns:
            bool: True wenn erfolgreich gespeichert
        """
        try:
            self.logger.info(f"💾 Speichere Gebäude nach: {output_path}")
            buildings_gdf.to_file(output_path, driver='ESRI Shapefile')
            self.logger.info("✅ Gebäude erfolgreich gespeichert")
            return True
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Speichern der Gebäude: {str(e)}")
            return False
    
    def load_buildings(self, input_path: Path) -> Optional[gpd.GeoDataFrame]:
        """Lädt Gebäude aus einem Shapefile.
        
        Args:
            input_path (Path): Der Eingabepfad
            
        Returns:
            Optional[gpd.GeoDataFrame]: Die geladenen Gebäude oder None bei Fehler
        """
        try:
            self.logger.info(f"📂 Lade Gebäude von: {input_path}")
            buildings_gdf = gpd.read_file(input_path)
            self.logger.info(f"✅ {len(buildings_gdf)} Gebäude geladen")
            return buildings_gdf
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Gebäude: {str(e)}")
            return None 
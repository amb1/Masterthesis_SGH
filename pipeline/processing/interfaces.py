"""
Interfaces für die Pipeline-Prozessoren.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import geopandas as gpd

class BuildingProcessorInterface(ABC):
    """Interface für Gebäudeprozessoren."""
    
    @abstractmethod
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den Prozessor.
        
        Args:
            config: Konfigurationsdaten
        """
        pass
    
    @abstractmethod
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Validiert die Gebäudedaten.
        
        Args:
            building_data: Gebäudedaten
            
        Returns:
            bool: True wenn gültig
        """
        pass
    
    @abstractmethod
    def process_building(self, building_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein einzelnes Gebäude.
        
        Args:
            building_data: Gebäudedaten
            
        Returns:
            Dict[str, Any]: Verarbeitete Gebäudedaten
        """
        pass 
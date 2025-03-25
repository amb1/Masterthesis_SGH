"""
Basisklassen für die CEA-Verarbeitung.
"""
from typing import Dict, Any, Optional
import logging

class CEAProcessingError(Exception):
    """Basisklasse für CEA-Verarbeitungsfehler"""
    pass

class CEABaseProcessor:
    """
    Basisklasse für alle CEA-Prozessoren.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def validate(self, data: Dict[str, Any]) -> bool:
        """
        Basisvalidierung für alle Prozessoren.
        """
        if not data:
            self.logger.error("Keine Daten zum Verarbeiten")
            return False
        return True
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Basisverarbeitungsmethode.
        """
        if not self.validate(data):
            return {}
        return data 
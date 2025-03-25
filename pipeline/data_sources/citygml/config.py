"""
CityGML-Konfigurationsklasse.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml

class CityGMLConfigError(Exception):
    """Fehler bei der CityGML-Konfiguration."""
    pass

class CityGMLConfig:
    """Konfigurationsklasse für CityGML-Verarbeitung."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """Initialisiert die CityGML-Konfiguration.
        
        Args:
            config: Optional[Dict] - Direkte Konfiguration
            config_path: Optional[str] - Pfad zur Konfigurationsdatei
        """
        self.logger = logging.getLogger(__name__)
        
        # Lade Konfiguration
        if config is not None:
            self.config = config
            self.logger.info("✅ CityGML-Konfiguration aus Dictionary geladen")
        elif config_path is not None:
            self.config = self._load_config_file(config_path)
            self.logger.info(f"✅ CityGML-Konfiguration geladen von: {config_path}")
        else:
            self.config = {}
            self.logger.warning("⚠️ Keine Konfiguration übergeben")
            
    def _load_config_file(self, config_path: str) -> Dict[str, Any]:
        """Lädt die Konfiguration aus einer Datei.
        
        Args:
            config_path: str - Pfad zur Konfigurationsdatei
            
        Returns:
            Dict[str, Any]: Geladene Konfiguration
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if not config:
                    self.logger.warning("⚠️ Leere Konfigurationsdatei")
                    return {}
                return config
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
            return {}
            
    def validate(self) -> bool:
        """Validiert die Konfiguration.
        
        Returns:
            bool: True wenn die Konfiguration gültig ist
        """
        try:
            # Prüfe Pflichtfelder
            required_sections = ['namespaces', 'required_fields', 'geometry', 'citygml_fields']
            for section in required_sections:
                if section not in self.config:
                    self.logger.warning(f"⚠️ Pflichtsektion '{section}' fehlt in der Konfiguration")
                    return False
                    
            # Prüfe Namespaces
            if not isinstance(self.config['namespaces'], dict):
                self.logger.warning("⚠️ Ungültige Namespace-Konfiguration")
                return False
                
            # Prüfe required_fields
            if not isinstance(self.config['required_fields'], list):
                self.logger.warning("⚠️ Ungültige required_fields-Konfiguration")
                return False
                
            # Prüfe Geometrie-Konfiguration
            geometry_config = self.config['geometry']
            if not isinstance(geometry_config, dict):
                self.logger.warning("⚠️ Ungültige Geometrie-Konfiguration")
                return False
                
            if 'srs_name' not in geometry_config:
                self.logger.warning("⚠️ Kein SRS-Name in Geometrie-Konfiguration")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Konfigurationsvalidierung: {str(e)}")
            return False
            
    @property
    def namespaces(self) -> Dict[str, str]:
        """Gibt die XML-Namespaces zurück."""
        return self.config.get('namespaces', {})
        
    @property
    def required_fields(self) -> List[str]:
        """Gibt die Pflichtfelder zurück."""
        return self.config.get('required_fields', [])
        
    @property
    def geometry_config(self) -> Dict[str, Any]:
        """Gibt die Geometrie-Konfiguration zurück."""
        return self.config.get('geometry', {})
        
    @property
    def field_config(self) -> Dict[str, Any]:
        """Gibt die Feldkonfiguration zurück."""
        return self.config.get('citygml_fields', {})
        
    @property
    def debug_enabled(self) -> bool:
        """Gibt zurück ob Debug-Modus aktiviert ist."""
        return self.config.get('debug', {}).get('enabled', False)
        
    @property
    def output_formats(self) -> List[str]:
        """Gibt die konfigurierten Ausgabeformate zurück."""
        return self.config.get('file_formats', []) 
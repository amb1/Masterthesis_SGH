import logging
from typing import Dict, Any, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

class ConfigManager:
    """Klasse für die Verwaltung von Konfigurationen"""
    
    def __init__(self, config_dir: Path):
        """Initialisiert den ConfigManager
        
        Args:
            config_dir (Path): Verzeichnis mit den Konfigurationsdateien
        """
        self.config_dir = config_dir
        self.configs = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def load_configs(self) -> bool:
        """Lädt alle Konfigurationsdateien
        
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Lade CEA-Konfiguration
            cea_config = self._load_yaml('cea_config.yml')
            if not cea_config:
                return False
                
            # Lade Feldzuordnungen
            field_mapping = self._load_yaml('field_mapping.yml')
            if not field_mapping:
                return False
                
            # Lade Standardwerte
            defaults = self._load_yaml('defaults.yml')
            if not defaults:
                return False
                
            # Lade Logging-Konfiguration
            logging_config = self._load_yaml('logging_config.yml')
            if not logging_config:
                return False
                
            # Kombiniere Konfigurationen
            self.configs = {
                'cea': cea_config,
                'mapping': field_mapping,
                'defaults': defaults,
                'logging': logging_config
            }
            
            self.logger.info("✅ Konfigurationen erfolgreich geladen")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Konfigurationen: {str(e)}")
            return False
            
    def _load_yaml(self, filename: str) -> Optional[Dict[str, Any]]:
        """Lädt eine YAML-Konfigurationsdatei
        
        Args:
            filename (str): Name der Konfigurationsdatei
            
        Returns:
            Optional[Dict[str, Any]]: Konfigurationsdictionary oder None
        """
        try:
            file_path = self.config_dir / filename
            if not file_path.exists():
                self.logger.error(f"❌ Konfigurationsdatei nicht gefunden: {file_path}")
                return None
                
            with open(file_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            self.logger.debug(f"✅ Konfiguration geladen: {filename}")
            return config
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Konfiguration {filename}: {str(e)}")
            return None
            
    def get_config(self, section: str) -> Optional[Dict[str, Any]]:
        """Gibt eine Konfigurationssektion zurück
        
        Args:
            section (str): Name der Konfigurationssektion
            
        Returns:
            Optional[Dict[str, Any]]: Konfigurationsdictionary oder None
        """
        try:
            if section not in self.configs:
                self.logger.error(f"❌ Konfigurationssektion nicht gefunden: {section}")
                return None
                
            return self.configs[section]
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen der Konfiguration {section}: {str(e)}")
            return None
            
    def get_field_mapping(self, source_field: str) -> Optional[str]:
        """Gibt die Zuordnung für ein Quellfeld zurück
        
        Args:
            source_field (str): Name des Quellfelds
            
        Returns:
            Optional[str]: Name des Zielfelds oder None
        """
        try:
            mapping = self.configs.get('mapping', {})
            if source_field not in mapping:
                self.logger.warning(f"⚠️ Keine Zuordnung gefunden für: {source_field}")
                return None
                
            return mapping[source_field]
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen der Feldzuordnung für {source_field}: {str(e)}")
            return None
            
    def get_default_value(self, field: str) -> Any:
        """Gibt den Standardwert für ein Feld zurück
        
        Args:
            field (str): Name des Felds
            
        Returns:
            Any: Standardwert
        """
        try:
            defaults = self.configs.get('defaults', {})
            if field not in defaults:
                self.logger.warning(f"⚠️ Kein Standardwert gefunden für: {field}")
                return None
                
            return defaults[field]
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen des Standardwerts für {field}: {str(e)}")
            return None
            
    def validate_configs(self) -> bool:
        """Überprüft die Konfigurationen auf Vollständigkeit
        
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            # Überprüfe erforderliche Konfigurationen
            required_configs = ['cea', 'mapping', 'defaults', 'logging']
            for config in required_configs:
                if config not in self.configs:
                    self.logger.error(f"❌ Fehlende Konfiguration: {config}")
                    return False
                    
            # Überprüfe CEA-Konfiguration
            cea_config = self.configs['cea']
            required_sections = ['fields', 'mapping']
            for section in required_sections:
                if section not in cea_config:
                    self.logger.error(f"❌ Fehlende CEA-Konfigurationssektion: {section}")
                    return False
                    
            # Überprüfe Feldzuordnungen
            mapping = self.configs['mapping']
            if not mapping:
                self.logger.error("❌ Keine Feldzuordnungen definiert")
                return False
                
            # Überprüfe Standardwerte
            defaults = self.configs['defaults']
            if not defaults:
                self.logger.error("❌ Keine Standardwerte definiert")
                return False
                
            self.logger.info("✅ Konfigurationen erfolgreich validiert")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Konfigurationsvalidierung: {str(e)}")
            return False 
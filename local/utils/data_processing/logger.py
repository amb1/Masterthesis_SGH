import logging
from typing import Dict, Any, Optional
from pathlib import Path
import yaml

class Logger:
    """Klasse für das Logging"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den Logger
        
        Args:
            config (Dict[str, Any]): Konfigurationsdictionary
        """
        self.config = config
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Richtet den Logger ein
        
        Returns:
            logging.Logger: Konfigurierter Logger
        """
        try:
            # Erstelle Logger
            logger = logging.getLogger('CEAProcessor')
            logger.setLevel(logging.DEBUG)
            
            # Erstelle Handler
            console_handler = logging.StreamHandler()
            file_handler = logging.FileHandler(self.config.get('log_file', 'cea_processor.log'))
            
            # Setze Log-Level
            console_handler.setLevel(logging.INFO)
            file_handler.setLevel(logging.DEBUG)
            
            # Erstelle Formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            
            # Füge Handler hinzu
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)
            
            return logger
            
        except Exception as e:
            print(f"❌ Fehler beim Einrichten des Loggers: {str(e)}")
            return logging.getLogger('CEAProcessor')
            
    def debug(self, message: str) -> None:
        """Loggt eine Debug-Nachricht
        
        Args:
            message (str): Nachricht
        """
        self.logger.debug(message)
        
    def info(self, message: str) -> None:
        """Loggt eine Info-Nachricht
        
        Args:
            message (str): Nachricht
        """
        self.logger.info(message)
        
    def warning(self, message: str) -> None:
        """Loggt eine Warnung
        
        Args:
            message (str): Nachricht
        """
        self.logger.warning(message)
        
    def error(self, message: str) -> None:
        """Loggt einen Fehler
        
        Args:
            message (str): Nachricht
        """
        self.logger.error(message)
        
    def critical(self, message: str) -> None:
        """Loggt einen kritischen Fehler
        
        Args:
            message (str): Nachricht
        """
        self.logger.critical(message)
        
    def log_data_validation(self, data: Dict[str, Any], validation_result: bool) -> None:
        """Loggt das Ergebnis der Datenvalidierung
        
        Args:
            data (Dict[str, Any]): Validierte Daten
            validation_result (bool): Validierungsergebnis
        """
        if validation_result:
            self.info("✅ Datenvalidierung erfolgreich")
        else:
            self.error("❌ Datenvalidierung fehlgeschlagen")
            self.debug(f"Ungültige Daten: {data}")
            
    def log_file_creation(self, file_path: Path, success: bool) -> None:
        """Loggt die Dateierstellung
        
        Args:
            file_path (Path): Pfad der erstellten Datei
            success (bool): Erfolg der Erstellung
        """
        if success:
            self.info(f"✅ Datei erstellt: {file_path}")
        else:
            self.error(f"❌ Fehler beim Erstellen der Datei: {file_path}")
            
    def log_error_handling(self, error_type: str, error_message: str, handled: bool) -> None:
        """Loggt die Fehlerbehandlung
        
        Args:
            error_type (str): Typ des Fehlers
            error_message (str): Fehlermeldung
            handled (bool): Ob der Fehler behandelt wurde
        """
        if handled:
            self.warning(f"⚠️ Fehler behandelt ({error_type}): {error_message}")
        else:
            self.error(f"❌ Fehler konnte nicht behandelt werden ({error_type}): {error_message}") 
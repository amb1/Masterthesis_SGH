"""
Basis-Klassen für die Pipeline-Komponenten
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional

class BaseConverter(ABC):
    """Basis-Klasse für alle Konverter"""
    
    @abstractmethod
    def convert(self, input_path: Path, output_path: Path) -> bool:
        """
        Konvertiert die Eingabedatei in das Zielformat.

        Args:
            input_path: Pfad zur Eingabedatei
            output_path: Pfad für die Ausgabe

        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        pass

class BaseExtractor(ABC):
    """Basis-Klasse für Metadaten-Extraktion"""
    
    @abstractmethod
    def extract(self, file_path: Path) -> Dict[str, Any]:
        """
        Extrahiert Metadaten aus der Datei.

        Args:
            file_path: Pfad zur Datei

        Returns:
            Dict[str, Any]: Extrahierte Metadaten
        """
        pass

class BaseStorage(ABC):
    """Basis-Klasse für Storage-Operationen"""
    
    @abstractmethod
    def store(self, data: Any, **kwargs) -> str:
        """
        Speichert Daten im Storage.

        Args:
            data: Zu speichernde Daten
            **kwargs: Zusätzliche Parameter

        Returns:
            str: ID oder URL der gespeicherten Daten
        """
        pass

    @abstractmethod
    def retrieve(self, id_or_url: str, **kwargs) -> Any:
        """
        Lädt Daten aus dem Storage.

        Args:
            id_or_url: ID oder URL der Daten
            **kwargs: Zusätzliche Parameter

        Returns:
            Any: Geladene Daten
        """
        pass 
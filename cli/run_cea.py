"""
CLI-Schnittstelle für die CEA-Datenverarbeitung.
"""

import click
from pathlib import Path
import logging
from typing import Optional
from pipeline.orchestrator import PipelineOrchestrator, PipelineError
from core.logging_config import setup_logging
import os

# Logger-Konfiguration
setup_logging()
logger = logging.getLogger(__name__)

class CEAProcessingError(Exception):
    """Basisklasse für CEA-Verarbeitungsfehler."""
    def __init__(self, message: str, details: Optional[Exception] = None):
        self.message = message
        self.details = details
        super().__init__(f"{message}" + (f": {str(details)}" if details else ""))

def validate_paths(config: str, data_dir: str, output_dir: str) -> tuple[Path, Path, Path]:
    """Validiert und erstellt die notwendigen Pfade.
    
    Args:
        config: Pfad zur Konfigurationsdatei
        data_dir: Eingabeverzeichnis
        output_dir: Ausgabeverzeichnis
        
    Returns:
        Tuple aus validierten Path-Objekten (config_path, data_path, output_path)
        
    Raises:
        CEAProcessingError: Wenn Pfade ungültig oder nicht erstellbar sind
    """
    # Validiere Konfigurationsdatei
    config_path = Path(config)
    if not config_path.exists():
        raise CEAProcessingError(f"Konfigurationsdatei nicht gefunden: {config}")
    if not config_path.is_file():
        raise CEAProcessingError(f"Konfigurationspfad ist keine Datei: {config}")
        
    # Validiere und erstelle Verzeichnisse
    data_path = Path(data_dir)
    output_path = Path(output_dir)
    
    try:
        for path in [data_path, output_path]:
            # Prüfe Schreibrechte im übergeordneten Verzeichnis
            if not path.exists() and not path.parent.exists():
                raise CEAProcessingError(f"Übergeordnetes Verzeichnis existiert nicht: {path.parent}")
            if not path.exists() and not os.access(path.parent, os.W_OK):
                raise CEAProcessingError(f"Keine Schreibrechte für: {path.parent}")
            
            path.mkdir(parents=True, exist_ok=True)
            
            # Prüfe Schreibrechte im erstellten Verzeichnis
            if not os.access(path, os.W_OK):
                raise CEAProcessingError(f"Keine Schreibrechte für: {path}")
                
    except PermissionError as e:
        raise CEAProcessingError("Keine Berechtigung zum Erstellen der Verzeichnisse", e)
    except Exception as e:
        raise CEAProcessingError("Fehler beim Erstellen der Verzeichnisse", e)
        
    return config_path, data_path, output_path

@click.command()
@click.option('--config', '-c', default='config/global.yml', help='Pfad zur Konfigurationsdatei')
@click.option('--data-dir', '-d', default='data', help='Verzeichnis mit Eingabedaten')
@click.option('--output-dir', '-o', default='outputs', help='Ausgabeverzeichnis')
def run_cea(config: str, data_dir: str, output_dir: str):
    """Führt die CEA-Datenverarbeitung durch."""
    try:
        # Validiere Eingabepfade
        config_path, data_path, output_path = validate_paths(config, data_dir, output_dir)

        # Konfiguriere Pipeline
        try:
            orchestrator = PipelineOrchestrator(config_path=str(config_path))
        except PipelineError as e:
            if "CityGML" in str(e):
                raise CEAProcessingError("CityGML-Eingabedatei fehlt in der Konfiguration", e)
            raise CEAProcessingError(f"Pipeline-Fehler: {e.message}", e)
        except Exception as e:
            raise CEAProcessingError("Fehler beim Initialisieren des Orchestrators", e)

        # Starte Verarbeitung
        logger.info("🚀 Starte CEA-Verarbeitung...")
        try:
            success = orchestrator.run_pipeline()
        except PipelineError as e:
            if "fetch_data" in str(e):
                raise CEAProcessingError("Fehler beim Laden der Eingabedaten", e)
            raise CEAProcessingError(f"Pipeline-Fehler: {e.message}", e)
        
        if success:
            logger.info("✅ CEA-Verarbeitung erfolgreich abgeschlossen")
        else:
            raise CEAProcessingError("Pipeline-Verarbeitung fehlgeschlagen")

    except CEAProcessingError as e:
        logger.error(f"❌ CEA-Verarbeitung mit Fehlern beendet: {e.message}")
        if e.details:
            logger.debug(f"Details: {str(e.details)}")
        raise click.Abort()
    except Exception as e:
        logger.error(f"❌ Unerwarteter Fehler bei der CEA-Verarbeitung: {str(e)}")
        logger.debug("Stacktrace:", exc_info=True)
        raise click.Abort()

if __name__ == "__main__":
    run_cea() 
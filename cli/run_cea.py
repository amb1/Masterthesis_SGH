"""
CLI-Schnittstelle für die CEA-Datenverarbeitung.
"""

import click
from pathlib import Path
from pipeline.orchestrator import PipelineOrchestrator
import logging

logger = logging.getLogger(__name__)

@click.command()
@click.option('--config', '-c', default='config/global.yml', help='Pfad zur Konfigurationsdatei')
@click.option('--data-dir', '-d', default='data', help='Verzeichnis mit Eingabedaten')
@click.option('--output-dir', '-o', default='outputs', help='Ausgabeverzeichnis')
def run_cea(config: str, data_dir: str, output_dir: str):
    """Führt die CEA-Datenverarbeitung durch."""
    try:
        # Konfiguriere Pipeline
        orchestrator = PipelineOrchestrator(config_path=config)
        
        # Setze Verzeichnisse
        data_path = Path(data_dir)
        output_path = Path(output_dir)
        
        # Stelle sicher, dass Verzeichnisse existieren
        data_path.mkdir(parents=True, exist_ok=True)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Führe Pipeline aus
        success = orchestrator.run_pipeline()
        
        if success:
            click.echo("✅ CEA-Verarbeitung erfolgreich abgeschlossen!")
        else:
            click.echo("❌ CEA-Verarbeitung mit Fehlern beendet", err=True)
            raise click.Abort()
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der CEA-Verarbeitung: {str(e)}")
        raise click.Abort()

if __name__ == '__main__':
    run_cea() 
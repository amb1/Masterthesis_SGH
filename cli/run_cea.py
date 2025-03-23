"""
CLI-Schnittstelle für die CEA-Datenverarbeitung.
"""

import click
from pathlib import Path
from pipeline.orchestrator import PipelineOrchestrator

@click.command()
@click.option('--config', '-c', default='config/global.yml', help='Pfad zur Konfigurationsdatei')
@click.option('--data-dir', '-d', default='data', help='Verzeichnis mit Eingabedaten')
@click.option('--output-dir', '-o', default='outputs', help='Ausgabeverzeichnis')
def run_cea(config: str, data_dir: str, output_dir: str):
    """Führt die CEA-Datenverarbeitung durch."""
    try:
        # Konfiguriere Pipeline
        orchestrator = PipelineOrchestrator(config)
        
        # Setze Verzeichnisse
        data_path = Path(data_dir)
        output_path = Path(output_dir)
        
        # Stelle sicher, dass Verzeichnisse existieren
        data_path.mkdir(parents=True, exist_ok=True)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Führe Pipeline aus
        orchestrator.run_pipeline()
        
        click.echo("CEA-Verarbeitung erfolgreich abgeschlossen!")
        
    except Exception as e:
        click.echo(f"Fehler bei der CEA-Verarbeitung: {str(e)}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    run_cea() 
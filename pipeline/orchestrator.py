"""
Pipeline-Orchestrator für die Verarbeitung von Gebäudedaten.

Dieser Orchestrator steuert den Datenfluss durch die verschiedenen
Verarbeitungsschritte der Pipeline.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List

from core.logging_config import setup_logging
from pipeline.data_sources.fetch_citygml import fetch_citygml_data
from pipeline.data_sources.fetch_wfs import fetch_wfs_data
from pipeline.processing.cea_mapper import process_cea_data
from pipeline.output.writer import write_output

class PipelineOrchestrator:
    def __init__(self, config_path: str = "config/global.yml"):
        self.config_path = Path(config_path)
        self.logger = setup_logging()
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Lädt die Pipeline-Konfiguration."""
        with open(self.config_path) as f:
            return yaml.safe_load(f)
    
    def _get_enabled_steps(self) -> List[str]:
        """Ermittelt die aktivierten Pipeline-Schritte."""
        steps = self.config.get("pipeline", {}).get("steps", [])
        return [step["name"] for step in steps if step.get("enabled", True)]
    
    def run_pipeline(self):
        """Führt die Pipeline-Verarbeitung durch."""
        try:
            self.logger.info("Starte Pipeline-Verarbeitung")
            enabled_steps = self._get_enabled_steps()
            
            # Fetch-Phase
            if "fetch_data" in enabled_steps:
                self.logger.info("Hole CityGML und WFS Daten")
                citygml_data = fetch_citygml_data()
                wfs_data = fetch_wfs_data()
            
            # Process-Phase
            if "process_data" in enabled_steps:
                self.logger.info("Verarbeite Daten für CEA")
                processed_data = process_cea_data(citygml_data, wfs_data)
            
            # Export-Phase
            if "export_data" in enabled_steps:
                self.logger.info("Exportiere Ergebnisse")
                write_output(processed_data)
            
            self.logger.info("Pipeline-Verarbeitung erfolgreich abgeschlossen")
            
        except Exception as e:
            self.logger.error(f"Fehler in der Pipeline: {str(e)}")
            raise

def main():
    orchestrator = PipelineOrchestrator()
    orchestrator.run_pipeline()

if __name__ == "__main__":
    main() 
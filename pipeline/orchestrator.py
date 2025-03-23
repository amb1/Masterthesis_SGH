"""
Pipeline-Orchestrator für die Verarbeitung von Gebäudedaten.

Dieser Orchestrator steuert den Datenfluss durch die verschiedenen
Verarbeitungsschritte der Pipeline.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from core.logging_config import setup_logging
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings
from pipeline.data_sources.wfs_fetcher import fetch_wfs_buildings
from pipeline.processing.cea_processor import CEABuildingProcessor
from pipeline.output.writer import write_output

logger = logging.getLogger(__name__)

class PipelineError(Exception):
    """Basisklasse für Pipeline-Fehler"""
    def __init__(self, message: str, step: str, details: Optional[Exception] = None):
        self.message = message
        self.step = step
        self.details = details
        super().__init__(f"{message} in Schritt '{step}'" + (f": {str(details)}" if details else ""))

class PipelineOrchestrator:
    def __init__(self, config_path: str = "config/global.yml"):
        """Initialisiert den Pipeline-Orchestrator.
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        self.config_path = Path(config_path)
        self.logger = setup_logging()
        self.config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Lädt die Pipeline-Konfiguration."""
        try:
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise PipelineError("Fehler beim Laden der Konfiguration", "config_load", e)
    
    def _get_enabled_steps(self) -> List[str]:
        """Ermittelt die aktivierten Pipeline-Schritte."""
        try:
            steps = self.config.get("pipeline", {}).get("steps", [])
            return [step["name"] for step in steps if step.get("enabled", True)]
        except Exception as e:
            raise PipelineError("Fehler beim Ermitteln der Pipeline-Schritte", "get_steps", e)
    
    def _fetch_data(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Holt die Daten aus den Quellen.
        
        Returns:
            Tuple mit CityGML und WFS Daten
        """
        try:
            self.logger.info("🔄 Hole CityGML Daten...")
            citygml_data = fetch_citygml_buildings()
            if not citygml_data:
                raise PipelineError("Keine CityGML Daten gefunden", "fetch_citygml")
                
            self.logger.info("🔄 Hole WFS Daten...")
            wfs_data = fetch_wfs_buildings()
            if not wfs_data:
                raise PipelineError("Keine WFS Daten gefunden", "fetch_wfs")
                
            return citygml_data, wfs_data
            
        except PipelineError:
            raise
        except Exception as e:
            raise PipelineError("Fehler beim Laden der Daten", "fetch_data", e)
    
    def _process_data(self, citygml_data: Dict[str, Any], wfs_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet die Daten für CEA.
        
        Args:
            citygml_data: CityGML Gebäudedaten
            wfs_data: WFS Gebäudedaten
            
        Returns:
            Verarbeitete Daten
        """
        try:
            self.logger.info("🔄 Verarbeite Daten für CEA...")
            processor = CEABuildingProcessor(self.config)
            processed_data = processor.process_buildings(citygml_data, wfs_data)
            
            if not processed_data:
                raise PipelineError("Keine Daten verarbeitet", "process_data")
                
            return processed_data
            
        except PipelineError:
            raise
        except Exception as e:
            raise PipelineError("Fehler bei der Datenverarbeitung", "process_data", e)
    
    def _export_data(self, processed_data: Dict[str, Any]) -> bool:
        """Exportiert die verarbeiteten Daten.
        
        Args:
            processed_data: Verarbeitete Daten
            
        Returns:
            True wenn erfolgreich exportiert
        """
        try:
            self.logger.info("🔄 Exportiere Ergebnisse...")
            success = write_output(processed_data)
            
            if not success:
                raise PipelineError("Fehler beim Exportieren der Daten", "export_data")
                
            return True
            
        except PipelineError:
            raise
        except Exception as e:
            raise PipelineError("Fehler beim Exportieren", "export_data", e)
    
    def run_pipeline(self) -> bool:
        """Führt die Pipeline-Verarbeitung durch.
        
        Returns:
            True wenn die Pipeline erfolgreich durchlaufen wurde
        """
        try:
            self.logger.info("🚀 Starte Pipeline-Verarbeitung")
            enabled_steps = self._get_enabled_steps()
            
            # Fetch-Phase
            if "fetch_data" in enabled_steps:
                citygml_data, wfs_data = self._fetch_data()
            
            # Process-Phase
            if "process_data" in enabled_steps:
                processed_data = self._process_data(citygml_data, wfs_data)
            
            # Export-Phase
            if "export_data" in enabled_steps:
                self._export_data(processed_data)
            
            self.logger.info("✅ Pipeline-Verarbeitung erfolgreich abgeschlossen")
            return True
            
        except PipelineError as e:
            self.logger.error(f"❌ {e.message} in Schritt '{e.step}'")
            if e.details:
                self.logger.debug(f"Details: {str(e.details)}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Unerwarteter Fehler in der Pipeline: {str(e)}")
            return False

def main():
    orchestrator = PipelineOrchestrator()
    orchestrator.run_pipeline()

if __name__ == "__main__":
    main() 
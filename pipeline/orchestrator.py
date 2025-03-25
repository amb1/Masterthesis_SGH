"""
Pipeline-Orchestrator für die Verarbeitung von Gebäudedaten.

Dieser Orchestrator steuert den Datenfluss durch die verschiedenen
Verarbeitungsschritte der Pipeline.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from core.logging_config import setup_logging, LoggedOperation
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings
from pipeline.data_sources.wfs_fetcher import fetch_wfs_buildings
from pipeline.data_sources.osm_fetcher import fetch_osm_data
from pipeline.processing.citygml_processor import CityGMLProcessor
from pipeline.processing.wfs_processor import WFSProcessor
from pipeline.processing.osm_processor import OSMProcessor
from pipeline.processing.cea_processor import CEABuildingProcessor
from pipeline.output.writer import write_output

# Konfiguriere Logging
setup_logging()
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
        self.logger = logging.getLogger(__name__)
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
    
    def _fetch_data(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Holt die Daten aus den Quellen.
        
        Returns:
            Tuple mit CityGML, WFS und OSM Daten
        """
        citygml_data = None
        wfs_data = None
        osm_data = None
        
        try:
            # Lade CityGML-Konfiguration
            citygml_config_path = self.config.get("data_source", {}).get("citygml", {}).get("config_file")
            if not citygml_config_path:
                raise PipelineError(
                    "Keine config_file in data_source.citygml konfiguriert",
                    "fetch_data"
                )
            
            try:
                with open(citygml_config_path, 'r', encoding='utf-8') as f:
                    citygml_config = yaml.safe_load(f)
                    
                # Füge die CityGML-Konfiguration zur globalen Konfiguration hinzu
                if 'data_source' not in self.config:
                    self.config['data_source'] = {}
                self.config['data_source']['citygml'].update(citygml_config)
                
            except Exception as e:
                raise PipelineError(
                    f"Fehler beim Laden der CityGML-Konfiguration: {str(e)}",
                    "fetch_data"
                )

            # Lade WFS-Konfiguration
            wfs_config_path = self.config.get("data_source", {}).get("wfs", {}).get("config_file")
            if not wfs_config_path:
                self.logger.warning("⚠️ Keine WFS-Konfiguration gefunden")
            else:
                try:
                    with open(wfs_config_path, 'r', encoding='utf-8') as f:
                        wfs_config = yaml.safe_load(f)
                    if 'data_source' not in self.config:
                        self.config['data_source'] = {}
                    if 'wfs' not in self.config['data_source']:
                        self.config['data_source']['wfs'] = {}
                    # Stelle sicher, dass die vienna_wfs Konfiguration korrekt übernommen wird
                    if 'vienna_wfs' in wfs_config:
                        self.config['data_source']['wfs'].update(wfs_config['vienna_wfs'])
                    else:
                        self.logger.error("❌ Keine vienna_wfs Konfiguration in der WFS-Konfigurationsdatei gefunden")
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Laden der WFS-Konfiguration: {str(e)}")
            
            base_path = Path(citygml_config.get("base_path", "data/raw/citygml"))
            default_file = citygml_config.get("default_file")
            
            if not base_path.exists():
                base_path.mkdir(parents=True, exist_ok=True)
                
            if not default_file:
                raise PipelineError(
                    "CityGML Dateiname nicht in Konfiguration definiert", 
                    "fetch_data"
                )
            
            citygml_file = base_path / default_file
            output_dir = Path(self.config.get("project", {}).get("paths", {}).get("output", "outputs"))
            
            with LoggedOperation("CityGML Daten abrufen"):
                citygml_data = fetch_citygml_buildings(
                    citygml_file=str(citygml_file),
                    output_dir=str(output_dir),
                    config=self.config
                )
                if citygml_data is None or citygml_data.empty:
                    raise PipelineError("Keine CityGML Daten gefunden", "fetch_citygml")
            
            with LoggedOperation("WFS Daten abrufen"):
                wfs_data = fetch_wfs_buildings(config=self.config.get('data_source', {}).get('wfs', {}))
                if wfs_data is None:
                    self.logger.warning("⚠️ Keine WFS Daten gefunden")
                    wfs_data = {}

            with LoggedOperation("OSM Daten abrufen"):
                # Hole Gebäude und Straßen von OSM
                osm_buildings = fetch_osm_data(
                    site_gdf=citygml_data,
                    data_type='buildings',
                    config=self.config.get('data_source', {}).get('osm', {})
                )
                osm_streets = fetch_osm_data(
                    site_gdf=citygml_data,
                    data_type='streets',
                    config=self.config.get('data_source', {}).get('osm', {})
                )
                osm_data = {
                    'buildings': osm_buildings,
                    'streets': osm_streets
                }
                
            return citygml_data, wfs_data, osm_data
            
        except Exception as e:
            if isinstance(e, PipelineError):
                raise
            raise PipelineError(
                f"Fehler beim Laden der Daten: {str(e)}", 
                "fetch_data",
                e
            )
    
    def _process_data(self, citygml_data: Dict[str, Any], wfs_data: Dict[str, Any], osm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet die Daten für CEA.
        
        Args:
            citygml_data: CityGML Gebäudedaten
            wfs_data: WFS Gebäudedaten
            osm_data: OSM Daten (Gebäude und Straßen)
            
        Returns:
            Verarbeitete Daten
        """
        try:
            # Lade CEA-Konfiguration
            cea_config_path = self.config.get("data_source", {}).get("cea", {}).get("config_file")
            if not cea_config_path:
                self.logger.warning("⚠️ Kein Konfigurationspfad für cea gefunden")
            else:
                try:
                    with open(cea_config_path, 'r', encoding='utf-8') as f:
                        cea_config = yaml.safe_load(f)
                    if 'data_source' not in self.config:
                        self.config['data_source'] = {}
                    if 'cea' not in self.config['data_source']:
                        self.config['data_source']['cea'] = {}
                    self.config['data_source']['cea'].update(cea_config)
                except Exception as e:
                    raise PipelineError("Fehler beim Laden der CEA-Konfiguration", "process_data", e)

            self.logger.info("🔄 Starte Datenverarbeitung...")
            
            # Initialisiere Prozessoren
            citygml_processor = CityGMLProcessor(self.config)
            wfs_processor = WFSProcessor(self.config)
            osm_processor = OSMProcessor(self.config)
            cea_processor = CEABuildingProcessor(self.config)
            
            # Verarbeite CityGML-Daten
            self.logger.info("🔄 Verarbeite CityGML-Daten...")
            processed_citygml = citygml_processor.process(citygml_data)
            if not processed_citygml:
                self.logger.warning("⚠️ Keine CityGML-Daten verarbeitet")
            
            # Verarbeite WFS-Daten
            self.logger.info("🔄 Verarbeite WFS-Daten...")
            processed_wfs = wfs_processor.process(wfs_data)
            if not processed_wfs:
                self.logger.warning("⚠️ Keine WFS-Daten verarbeitet")
            
            # Verarbeite OSM-Daten
            self.logger.info("🔄 Verarbeite OSM-Daten...")
            processed_osm = osm_processor.process(osm_data)
            if not processed_osm:
                self.logger.warning("⚠️ Keine OSM-Daten verarbeitet")
            
            # Kombiniere alle Daten für CEA-Verarbeitung
            combined_data = {
                'citygml': processed_citygml.get('buildings', {}),
                'wfs': processed_wfs.get('buildings', {}),
                'osm': {
                    'buildings': processed_osm.get('buildings', {}),
                    'streets': processed_osm.get('streets', {})
                }
            }
            
            # Verarbeite kombinierte Daten mit CEA-Prozessor
            self.logger.info("🔄 Führe CEA-Verarbeitung durch...")
            processed_data = cea_processor.process_buildings(
                combined_data['citygml'],
                combined_data['wfs'],
                combined_data['osm']
            )
            
            if not processed_data:
                raise PipelineError("Keine Daten verarbeitet", "process_data")
                
            self.logger.info("✅ Datenverarbeitung erfolgreich abgeschlossen")
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
                citygml_data, wfs_data, osm_data = self._fetch_data()
            
            # Process-Phase
            if "process_data" in enabled_steps:
                processed_data = self._process_data(citygml_data, wfs_data, osm_data)
            
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
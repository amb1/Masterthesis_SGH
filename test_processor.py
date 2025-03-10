import logging
from pathlib import Path
import sys

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent / "local"
sys.path.append(str(root_dir))

from utils.data_processing.base_building_processor import BuildingProcessorInterface
from utils.data_processing.config_loader import load_config
from utils.data_sources.fetch_wfs_data import ViennaWFS

def test_processor_workflow():
    try:
        logger.info("🔄 Starte Test des Building Processor Workflows")
        
        # Lade Konfiguration
        config_path = root_dir / "cfg" / "project_config.yml"
        logger.info(f"📂 Lade Konfiguration von: {config_path}")
        config = load_config(config_path)
        
        if not config:
            logger.error("❌ Keine gültige Konfiguration gefunden")
            return False
            
        # Initialisiere Processor
        logger.info("🔄 Initialisiere Building Processor")
        processor = BuildingProcessorInterface(str(config_path))
        
        # Teste CityGML-Verarbeitung
        citygml_path = root_dir / "data" / "inputs" / "citygml" / "099082.gml"
        logger.info(f"🔄 Verarbeite CityGML-Datei: {citygml_path}")
        
        if not citygml_path.exists():
            logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            return False
        
        # Verarbeite CityGML
        processor.process_citygml(str(citygml_path))
        
        if processor.buildings_gdf is None:
            logger.error("❌ Keine Gebäude aus CityGML extrahiert")
            return False
            
        logger.info(f"✅ {len(processor.buildings_gdf)} Gebäude aus CityGML extrahiert")
        
        # Überprüfe WFS-Integration
        if not processor.wfs_data:
            logger.warning("⚠️ Keine WFS-Daten geladen")
        else:
            logger.info(f"✅ WFS-Daten für {len(processor.wfs_data)} Layer geladen")
            
        # Speichere Ergebnisse
        output_dir = root_dir / "data" / "outputs" / "buildings"
        logger.info(f"💾 Speichere Ergebnisse nach: {output_dir}")
        processor.save_buildings(str(output_dir))
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler im Test-Workflow: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_processor_workflow()
    if success:
        logger.info("✅ Test-Workflow erfolgreich abgeschlossen")
    else:
        logger.error("❌ Test-Workflow fehlgeschlagen") 
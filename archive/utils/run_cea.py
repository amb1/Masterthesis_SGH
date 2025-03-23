"""
CLI-Entry-Point für CEA-Projekte.

Dieses Modul dient als Haupteinstiegspunkt für die CEA-Datenverarbeitung
und orchestriert die verschiedenen Verarbeitungsschritte.
"""

import argparse
import logging
import sys
from pathlib import Path

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent
sys.path.append(str(local_dir))

from utils.project_manager import (
    get_project_info,
    setup_project_structure,
    validate_project_structure
)
from utils.data_processor import process_building_data
from utils.config_manager import load_project_config

def parse_args():
    """Verarbeitet Kommandozeilenargumente"""
    parser = argparse.ArgumentParser(
        description="CEA Datenverarbeitung für Wien",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--project-name',
        help='Name des CEA-Projekts'
    )
    
    parser.add_argument(
        '--scenario-name',
        help='Name des Szenarios'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Überschreibe existierendes Szenario ohne Nachfrage'
    )
    
    return parser.parse_args()

def main():
    """Hauptfunktion für die CEA-Datenverarbeitung"""
    try:
        # Argumente verarbeiten
        args = parse_args()
        
        # Projekt-Info holen
        project_name, scenario_name, project_path, scenario_path = get_project_info(args)
        logger.info(f"🚀 Starte Verarbeitung für Projekt '{project_name}', Szenario '{scenario_name}'")
        
        # Projektstruktur erstellen
        created_dirs = setup_project_structure(project_path, scenario_path)
        if not created_dirs:
            logger.error("❌ Fehler beim Erstellen der Projektstruktur")
            sys.exit(1)
            
        # Konfiguration laden
        config = load_project_config(project_path)
        logger.info("✅ Konfiguration geladen")
        
        # Daten verarbeiten
        buildings, errors = process_building_data(scenario_path, config)
        
        # Fehler ausgeben
        if errors:
            logger.warning("\n⚠️ Folgende Fehler sind aufgetreten:")
            for error in errors:
                logger.warning(f"- {error['source']}: {error['error']}")
                
        # Ergebnis validieren
        if buildings.empty:
            logger.error("❌ Keine Gebäudedaten verarbeitet")
            sys.exit(1)
            
        # Projektstruktur validieren
        if not validate_project_structure(project_path, scenario_path):
            logger.error("❌ Ungültige Projektstruktur")
            sys.exit(1)
            
        logger.info(f"✅ Verarbeitung abgeschlossen - {len(buildings)} Gebäude verarbeitet")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Verarbeitung abgebrochen")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Verarbeitung: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main() 
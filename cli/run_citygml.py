#!/usr/bin/env python3
"""
CLI-Tool zum Verarbeiten von CityGML-Dateien.
"""

import sys
import logging
from pathlib import Path
from core.config_manager import load_config
from core.project_paths import get_output_path, get_config_path
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings

# Konfiguriere Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(handler)

def main():
    """Hauptfunktion für die CityGML-Verarbeitung."""
    try:
        # Lade Konfiguration
        config_path = get_config_path() / "global.yml"
        logger.info(f"📂 Suche Konfiguration in: {config_path}")
        config = load_config(config_path)
        
        if not config:
            logger.error("❌ Keine gültige Konfiguration gefunden")
            sys.exit(1)
        
        # Hole CityGML-Konfiguration
        citygml_config = config.get('data_source', {}).get('citygml', {})
        if not citygml_config:
            logger.error("❌ Keine CityGML-Konfiguration gefunden")
            sys.exit(1)
            
        # Konstruiere Pfade
        citygml_path = Path(citygml_config['input_file'])
        if not citygml_path.is_absolute():
            citygml_path = get_config_path().parent / citygml_path
            
        output_dir = get_output_path("citygml")
        
        # Überprüfe Pfade
        if not citygml_path.exists():
            logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            sys.exit(1)
            
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Ausgabeverzeichnis bereit: {output_dir}")
        
        # Extrahiere Gebäude
        buildings_gdf = fetch_citygml_buildings(str(citygml_path), str(output_dir), config)
        
        if buildings_gdf is not None:
            logger.info(f"✅ {len(buildings_gdf)} Gebäude extrahiert")
        else:
            logger.error("❌ Fehler beim Extrahieren der Gebäude")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fehler im Hauptprogramm: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
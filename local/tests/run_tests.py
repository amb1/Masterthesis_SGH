import os
import sys
from pathlib import Path
import logging
import importlib.util
import time

# Konfiguriere Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_test_module(module_name: str) -> bool:
    """Führt einen Test-Modul aus und gibt True zurück, wenn erfolgreich"""
    try:
        logger.info(f"\n{'='*50}")
        logger.info(f"Starte Test: {module_name}")
        logger.info(f"{'='*50}\n")
        
        start_time = time.time()
        
        # Importiere und führe das Test-Modul aus
        spec = importlib.util.spec_from_file_location(
            module_name,
            Path(__file__).parent / f"{module_name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        duration = time.time() - start_time
        logger.info(f"\n✅ Test {module_name} erfolgreich abgeschlossen (Dauer: {duration:.2f}s)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler in Test {module_name}: {str(e)}", exc_info=True)
        return False

def main():
    """Führt alle Tests aus"""
    try:
        # Liste der Test-Module
        test_modules = [
            "test_wfs_data",
            "test_citygml",
            "test_osm"
        ]
        
        # Führe Tests aus
        results = []
        for module in test_modules:
            success = run_test_module(module)
            results.append((module, success))
        
        # Zusammenfassung
        logger.info("\n" + "="*50)
        logger.info("TEST ZUSAMMENFASSUNG")
        logger.info("="*50)
        
        for module, success in results:
            status = "✅" if success else "❌"
            logger.info(f"{status} {module}")
            
        # Gesamtergebnis
        all_successful = all(success for _, success in results)
        if all_successful:
            logger.info("\n✨ Alle Tests erfolgreich abgeschlossen!")
        else:
            logger.error("\n❌ Einige Tests sind fehlgeschlagen!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Ausführen der Tests: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 
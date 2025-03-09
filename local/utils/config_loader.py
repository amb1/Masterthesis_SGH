import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_config(config_path: Path) -> dict:
    """Lädt die Konfiguration aus einer YAML-Datei
    
    Args:
        config_path: Pfad zur Konfigurationsdatei
    """
    try:
        logger.info(f"📂 Lade Konfiguration: {config_path.name}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        return config
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        return None

def main():
    """Test-Ausführung"""
    try:
        logger.info("🔍 Starte Config-Loader Test...")
        
        # Teste WFS-Konfiguration
        wfs_config_path = Path(__file__).resolve().parent.parent / "cfg" / "wfs" / "wfs_config.yml"
        logger.info(f"📂 Lade WFS-Konfiguration: {wfs_config_path}")
        
        config = load_config(wfs_config_path)
        if config:
            logger.info("✅ Konfiguration erfolgreich geladen")
            logger.info("\n📊 Verfügbare Layer:")
            for layer in config.get('vienna_wfs', {}).get('layer_definitions', {}):
                logger.info(f"- {layer}")
        else:
            logger.warning("⚠️ Keine Konfiguration geladen!")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main() 
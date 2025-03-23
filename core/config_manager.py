"""
Konfigurationsmanager-Modul für die Pipeline.

Migrated from local/utils/config_loader.py

Dieses Modul stellt Funktionen zum Laden und Validieren von
YAML-Konfigurationsdateien bereit.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, NamedTuple, Union
from core.logging_config import LoggedOperation
import logging

logger = logging.getLogger(__name__)

class ValidationResult(NamedTuple):
    """Ergebnis der Konfigurationsvalidierung."""
    is_valid: bool
    errors: list[str]

def load_config(config_file: Union[str, Path]) -> Dict[str, Any]:
    """Lädt eine YAML-Konfigurationsdatei.
    
    Args:
        config_file: Pfad zur Konfigurationsdatei
    
    Returns:
        Dictionary mit der Konfiguration
    
    Raises:
        FileNotFoundError: Wenn die Datei nicht existiert
        yaml.YAMLError: Bei ungültigem YAML-Format
        ValueError: Bei ungültigem Dateiformat
    """
    try:
        with LoggedOperation("Konfiguration laden"):
            config_path = Path(config_file) if isinstance(config_file, str) else config_file
            
            if not config_path.exists():
                raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
            
            if not str(config_path).endswith(('.yml', '.yaml')):
                raise ValueError("Ungültiges Dateiformat")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config = yaml.safe_load(f)
                    if not config:
                        raise ValueError("Leere Konfigurationsdatei")
                    logger.info(f"✅ Konfiguration geladen: {config_path}")
                    return config
                except yaml.YAMLError:
                    raise ValueError("YAML Syntax-Fehler")
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        raise

def validate_config(config: Dict[str, Any]) -> ValidationResult:
    """Validiert eine Konfiguration.
    
    Args:
        config: Zu validierende Konfiguration
    
    Returns:
        ValidationResult mit Validierungsstatus und Fehlern
    """
    try:
        with LoggedOperation("Konfiguration validieren"):
            errors = []
            
            # Validiere cea_workflow
            if 'cea_workflow' not in config:
                errors.append("Fehlender Schlüssel: cea_workflow")
            else:
                workflow = config['cea_workflow']
                if 'scripts' not in workflow:
                    errors.append("Fehlender Schlüssel: cea_workflow.scripts")
                else:
                    for i, script in enumerate(workflow['scripts']):
                        if 'name' not in script:
                            errors.append(f"Fehlender Schlüssel: name in Script {i}")
                        if 'parameters' not in script:
                            errors.append(f"Fehlender Schlüssel: parameters in Script {i}")
            
            return ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors
            )
    except Exception as e:
        logger.error(f"❌ Fehler bei der Konfigurationsvalidierung: {str(e)}")
        raise

def get_config_path(config_name: str) -> Path:
    """Ermittelt den absoluten Pfad zu einer Konfigurationsdatei.
    
    Args:
        config_name: Name der Konfigurationsdatei (z.B. 'wfs/stream_config.yml')
        
    Returns:
        Absoluter Pfad zur Konfigurationsdatei
    """
    try:
        with LoggedOperation("Konfigurationspfad ermitteln"):
            # Basisverzeichnis für Konfigurationen
            config_dir = Path(__file__).resolve().parent.parent / "config"
            
            # Füge .yml Erweiterung hinzu, wenn nicht vorhanden
            if not config_name.endswith(('.yml', '.yaml')):
                config_name += '.yml'
            
            config_path = config_dir / config_name
            
            if not config_path.exists():
                raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_path}")
                
            return config_path
    except Exception as e:
        logger.error(f"❌ Fehler beim Ermitteln des Konfigurationspfads: {str(e)}")
        raise

def main():
    """Test-Ausführung"""
    try:
        logger.info("🔍 Starte Config-Manager Test...")
        
        # Teste WFS-Konfiguration
        wfs_config_path = get_config_path("wfs/stream_config.yml")
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
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    main() 
"""
Konfigurationsmanager-Modul für die Pipeline.

Dieses Modul stellt Funktionen zum Laden und Validieren von
YAML-Konfigurationsdateien bereit.
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, NamedTuple, Union, Optional
from core.logging_config import LoggedOperation
import logging

logger = logging.getLogger(__name__)

class ValidationResult(NamedTuple):
    """Ergebnis der Konfigurationsvalidierung."""
    is_valid: bool
    errors: list[str]

def load_config(config_file: Union[str, Path], load_referenced: bool = True) -> Dict[str, Any]:
    """Lädt eine YAML-Konfigurationsdatei und optional referenzierte Konfigurationen.
    
    Args:
        config_file: Pfad zur Konfigurationsdatei
        load_referenced: Wenn True, werden referenzierte Konfigurationen auch geladen
    
    Returns:
        Dictionary mit der Konfiguration
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
                    
                    # Lade referenzierte Konfigurationen
                    if load_referenced and 'config_files' in config:
                        config['_referenced'] = {}
                        for key, ref_path in config['config_files'].items():
                            ref_config_path = get_config_path(ref_path)
                            ref_config = load_config(ref_config_path, load_referenced=False)
                            config['_referenced'][key] = ref_config
                    
                    logger.info(f"✅ Konfiguration geladen: {config_path}")
                    return config
                except yaml.YAMLError:
                    raise ValueError("YAML Syntax-Fehler")
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        raise

def get_module_config(global_config: Dict[str, Any], module_name: str) -> Optional[Dict[str, Any]]:
    """Holt die Konfiguration für ein spezifisches Modul.
    
    Args:
        global_config: Globale Konfiguration
        module_name: Name des Moduls (z.B. 'citygml', 'wfs', etc.)
    
    Returns:
        Modulspezifische Konfiguration oder None
    """
    try:
        # Prüfe zuerst in referenzierten Konfigurationen
        if '_referenced' in global_config and module_name in global_config['_referenced']:
            return global_config['_referenced'][module_name]
        
        # Fallback: Suche direkt in der globalen Konfiguration
        if module_name in global_config:
            return global_config[module_name]
        
        return None
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Modulkonfiguration: {str(e)}")
        return None

def get_config_path(config_name: str) -> Path:
    """Ermittelt den absoluten Pfad zu einer Konfigurationsdatei.
    
    Args:
        config_name: Name der Konfigurationsdatei (z.B. 'config/wfs/stream_config.yml')
        
    Returns:
        Absoluter Pfad zur Konfigurationsdatei
    """
    try:
        with LoggedOperation("Konfigurationspfad ermitteln"):
            # Basisverzeichnis für Konfigurationen
            root_dir = Path(__file__).resolve().parent.parent
            
            # Wenn der Pfad nicht mit 'config/' beginnt, füge es hinzu
            if not config_name.startswith('config/'):
                config_name = f"config/{config_name}"
            
            # Füge .yml Erweiterung hinzu, wenn nicht vorhanden
            if not config_name.endswith(('.yml', '.yaml')):
                config_name += '.yml'
            
            config_path = root_dir / config_name
            
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
        
        # Lade globale Konfiguration
        global_config = load_config(get_config_path("global.yml"))
        
        # Teste Zugriff auf Modulkonfigurationen
        for module in ['citygml', 'wfs', 'cea', 'osm']:
            config = get_module_config(global_config, module)
            if config:
                logger.info(f"✅ {module}-Konfiguration erfolgreich geladen")
            else:
                logger.warning(f"⚠️ Keine Konfiguration für {module} gefunden")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        raise

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    main() 
"""
Konfigurationsmanager für CEA-Projekte.

Dieses Modul enthält Funktionen zum Laden und Validieren von Konfigurationsdateien.
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

# Logger konfigurieren
logger = logging.getLogger(__name__)

def load_config(config_file: str) -> Dict[str, Any]:
    """Lädt eine YAML-Konfigurationsdatei.
    
    Args:
        config_file: Pfad zur Konfigurationsdatei
        
    Returns:
        Dict[str, Any]: Dictionary mit der Konfiguration
        
    Raises:
        FileNotFoundError: Wenn die Datei nicht existiert
        yaml.YAMLError: Bei ungültigem YAML-Format
        ValueError: Bei ungültigem Dateiformat
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {config_file}")
        
    if not str(config_file).endswith(('.yml', '.yaml')):
        raise ValueError("Ungültiges Dateiformat - nur .yml oder .yaml erlaubt")
        
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            
        if not config:
            raise ValueError("Leere Konfigurationsdatei")
            
        return config
        
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML Syntax-Fehler: {str(e)}")
        
    except Exception as e:
        raise ValueError(f"Fehler beim Laden der Konfiguration: {str(e)}")

def validate_config(config: Dict[str, Any]) -> bool:
    """Validiert die Konfiguration
    
    Args:
        config: Konfigurationsdaten
        
    Returns:
        bool: True wenn gültig, False sonst
        
    Raises:
        ValueError: Bei ungültiger Konfiguration
    """
    required_sections = ['citygml', 'wfs', 'osm', 'cea']
    
    # Überprüfe erforderliche Abschnitte
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Erforderlicher Konfigurationsabschnitt fehlt: {section}")
            
    # Validiere CityGML-Konfiguration
    citygml_config = config['citygml']
    if not isinstance(citygml_config, dict):
        raise ValueError("Ungültige CityGML-Konfiguration")
        
    required_citygml = ['input_file', 'output_format']
    for key in required_citygml:
        if key not in citygml_config:
            raise ValueError(f"Erforderlicher CityGML-Parameter fehlt: {key}")
            
    # Validiere WFS-Konfiguration
    wfs_config = config['wfs']
    if not isinstance(wfs_config, dict):
        raise ValueError("Ungültige WFS-Konfiguration")
        
    required_wfs = ['url', 'layer', 'version']
    for key in required_wfs:
        if key not in wfs_config:
            raise ValueError(f"Erforderlicher WFS-Parameter fehlt: {key}")
            
    # Validiere OSM-Konfiguration
    osm_config = config['osm']
    if not isinstance(osm_config, dict):
        raise ValueError("Ungültige OSM-Konfiguration")
        
    if 'buffer_distance' not in osm_config:
        raise ValueError("Erforderlicher OSM-Parameter fehlt: buffer_distance")
        
    # Validiere CEA-Konfiguration
    cea_config = config['cea']
    if not isinstance(cea_config, dict):
        raise ValueError("Ungültige CEA-Konfiguration")
        
    required_cea = ['building_types', 'construction_periods']
    for key in required_cea:
        if key not in cea_config:
            raise ValueError(f"Erforderlicher CEA-Parameter fehlt: {key}")
            
    return True

def get_config_paths(project_path: Path) -> Dict[str, Path]:
    """Ermittelt die Pfade zu den Konfigurationsdateien
    
    Args:
        project_path: Pfad zum Projektverzeichnis
        
    Returns:
        Dict[str, Path]: Dictionary mit den Konfigurationspfaden
    """
    config_dir = project_path / 'config'
    
    return {
        'citygml': config_dir / 'citygml.yml',
        'wfs': config_dir / 'wfs.yml',
        'osm': config_dir / 'osm.yml',
        'cea': config_dir / 'cea.yml'
    }

def load_project_config(project_path: Path) -> Dict[str, Any]:
    """Lädt die Projektkonfiguration
    
    Args:
        project_path: Pfad zum Projektverzeichnis
        
    Returns:
        Dict[str, Any]: Zusammengeführte Konfiguration
        
    Raises:
        FileNotFoundError: Wenn Konfigurationsdateien fehlen
        ValueError: Bei ungültiger Konfiguration
    """
    config_paths = get_config_paths(project_path)
    config = {}
    
    # Lade und validiere einzelne Konfigurationen
    for section, path in config_paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Konfigurationsdatei nicht gefunden: {path}")
            
        section_config = load_config(str(path))
        config[section] = section_config
        
    # Validiere Gesamtkonfiguration
    validate_config(config)
    
    return config

import pytest
from pathlib import Path
from core.config_manager import load_config, get_module_config

def test_osm_config_loading():
    """Testet das Laden der OSM-Konfiguration."""
    # Lade globale Konfiguration
    config = load_config("config/global.yml")
    assert config is not None
    
    # Hole OSM-Konfiguration
    osm_config = get_module_config(config, 'osm')
    assert osm_config is not None
    
    # Prüfe Struktur
    assert 'bbox' in osm_config
    assert 'filters' in osm_config
    assert 'defaults' in osm_config
    assert 'cache' in osm_config
    assert 'output' in osm_config
    
    # Prüfe spezifische Werte
    assert osm_config['bbox']['min_lat'] == 48.1
    assert osm_config['bbox']['max_lat'] == 48.3
    assert osm_config['defaults']['buildings']['height'] == 10
    
    # Prüfe Output-Formate
    assert len(osm_config['output']['formats']) == 2
    assert osm_config['output']['formats'][0]['type'] == 'geojson'
    assert osm_config['output']['formats'][1]['type'] == 'shp'

def test_config_references():
    """Testet die Referenzierung von Konfigurationsdateien."""
    config = load_config("config/global.yml")
    
    # Prüfe config_files Block
    assert 'config_files' in config
    assert all(key in config['config_files'] for key in ['osm', 'wfs', 'cea', 'citygml'])
    
    # Prüfe dass keine direkten Modulkonfigurationen in global.yml sind
    assert 'data_source' not in config
    assert 'wfs' not in config
    assert 'cea' not in config
    assert 'citygml' not in config

def test_module_config_loading():
    """Testet das Laden aller Modulkonfigurationen."""
    config = load_config("config/global.yml")
    
    for module in ['osm', 'wfs', 'cea', 'citygml']:
        module_config = get_module_config(config, module)
        assert module_config is not None, f"Konfiguration für {module} nicht gefunden"
        assert isinstance(module_config, dict), f"Konfiguration für {module} ist kein Dictionary"
        
        # Prüfe dass die Konfiguration nicht verschachtelt ist
        assert module not in module_config, f"Konfiguration für {module} ist unnötig verschachtelt" 
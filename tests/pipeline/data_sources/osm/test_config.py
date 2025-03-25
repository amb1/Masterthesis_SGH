"""
Tests für die OSM-Konfiguration.
"""

import pytest
from pathlib import Path
from pipeline.data_sources.osm.config import OSMConfig

def test_config_initialization():
    """Test der Konfigurationsinitialisierung."""
    config = OSMConfig()
    assert isinstance(config, OSMConfig)
    assert hasattr(config, '_config')
    
def test_config_with_custom_values():
    """Test der Konfiguration mit benutzerdefinierten Werten."""
    custom_config = {
        'buildings': {
            'buffer_distance': 200,
            'defaults': {
                'height': 12,
                'floors': 4
            }
        },
        'streets': {
            'street_types': {
                'primary': {},
                'secondary': {}
            },
            'network_type': 'drive'
        }
    }
    
    config = OSMConfig(custom_config)
    assert config.buffer_distance == 200
    assert config.building_defaults.get('height') == 12
    assert config.building_defaults.get('floors') == 4
    assert 'primary' in config.street_types
    assert config.network_type == 'drive'
    
def test_default_values():
    """Test der Standardwerte."""
    config = OSMConfig()
    assert config.buffer_distance == 100  # Standardwert
    assert isinstance(config.building_defaults, dict)
    assert isinstance(config.street_types, dict)
    assert config.network_type == 'all'  # Standardwert
    
def test_invalid_config():
    """Test mit ungültiger Konfiguration."""
    invalid_config = {'invalid': 'config'}
    config = OSMConfig(invalid_config)
    
    # Sollte Standardwerte verwenden
    assert config.buffer_distance == 100
    assert isinstance(config.building_defaults, dict)
    assert isinstance(config.street_types, dict) 
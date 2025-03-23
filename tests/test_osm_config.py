import pytest
import yaml
from pathlib import Path
from core.config_manager import load_config

@pytest.fixture
def sample_osm_config():
    """Erstellt eine Beispiel-OSM-Konfiguration für Tests."""
    return {
        'general': {
            'bbox': [0, 0, 100, 100],
            'filters': {},
            'cache': {
                'enabled': True,
                'directory': 'cache'
            }
        },
        'buildings': {
            'tags': {
                'building': True
            },
            'filters': {},
            'defaults': {
                'height': 10,
                'floors': 3,
                'year': 1990,
                'category': 'residential',
                'REFERENCE': ''
            }
        },
        'streets': {
            'tags': {
                'highway': ['residential', 'primary', 'secondary']
            },
            'filters': {},
            'defaults': {
                'width': 5,
                'lanes': 2,
                'surface': 'asphalt',
                'REFERENCE': ''
            }
        }
    }

@pytest.fixture
def config_file(tmp_path, sample_osm_config):
    """Erstellt eine temporäre Konfigurationsdatei."""
    config_path = tmp_path / 'config' / 'osm' / 'config.yml'
    config_path.parent.mkdir(parents=True)
    
    with open(config_path, 'w') as f:
        yaml.dump(sample_osm_config, f)
    
    return config_path

def test_load_osm_config(config_file):
    """Test des Ladens der OSM-Konfiguration."""
    config = load_config(config_file)
    
    # Überprüfe, ob die Konfiguration korrekt geladen wurde
    assert isinstance(config, dict)
    assert 'general' in config
    assert 'buildings' in config
    assert 'streets' in config
    
    # Überprüfe die Gebäude-Konfiguration
    assert 'tags' in config['buildings']
    assert 'filters' in config['buildings']
    assert 'defaults' in config['buildings']
    
    # Überprüfe die Straßen-Konfiguration
    assert 'tags' in config['streets']
    assert 'filters' in config['streets']
    assert 'defaults' in config['streets']

def test_building_config_structure(config_file):
    """Test der Struktur der Gebäude-Konfiguration."""
    config = load_config(config_file)
    building_config = config['buildings']
    
    # Überprüfe die Gebäude-Tags
    assert building_config['tags']['building'] is True
    
    # Überprüfe die Standardwerte
    defaults = building_config['defaults']
    assert defaults['height'] == 10
    assert defaults['floors'] == 3
    assert defaults['year'] == 1990
    assert defaults['category'] == 'residential'
    assert defaults['REFERENCE'] == ''

def test_street_config_structure(config_file):
    """Test der Struktur der Straßen-Konfiguration."""
    config = load_config(config_file)
    street_config = config['streets']
    
    # Überprüfe die Straßen-Tags
    assert 'highway' in street_config['tags']
    assert isinstance(street_config['tags']['highway'], list)
    assert 'residential' in street_config['tags']['highway']
    assert 'primary' in street_config['tags']['highway']
    assert 'secondary' in street_config['tags']['highway']
    
    # Überprüfe die Standardwerte
    defaults = street_config['defaults']
    assert defaults['width'] == 5
    assert defaults['lanes'] == 2
    assert defaults['surface'] == 'asphalt'
    assert defaults['REFERENCE'] == ''

def test_general_config_structure(config_file):
    """Test der Struktur der allgemeinen Konfiguration."""
    config = load_config(config_file)
    general_config = config['general']
    
    # Überprüfe die Bounding Box
    assert isinstance(general_config['bbox'], list)
    assert len(general_config['bbox']) == 4
    assert all(isinstance(x, (int, float)) for x in general_config['bbox'])
    
    # Überprüfe die Cache-Konfiguration
    assert 'cache' in general_config
    assert general_config['cache']['enabled'] is True
    assert general_config['cache']['directory'] == 'cache'

def test_osm_config_structure(osm_config):
    """Test der grundlegenden OSM-Konfigurationsstruktur."""
    # Überprüfe, ob die Hauptschlüssel vorhanden sind
    assert 'osm' in osm_config
    assert 'buildings' in osm_config['osm']
    assert 'streets' in osm_config['osm']
    
    # Überprüfe gemeinsame Einstellungen
    common_settings = ['bbox', 'filters', 'defaults', 'cache']
    for setting in common_settings:
        assert setting in osm_config['osm']

def test_buildings_config(osm_config):
    """Test der Gebäude-Konfiguration."""
    buildings_config = osm_config['osm']['buildings']
    
    # Überprüfe erforderliche Gebäude-Einstellungen
    required_settings = ['tags', 'filters', 'defaults']
    for setting in required_settings:
        assert setting in buildings_config
    
    # Überprüfe Standardwerte
    defaults = buildings_config['defaults']
    assert 'height' in defaults
    assert 'floors' in defaults
    assert 'year' in defaults
    assert 'category' in defaults

def test_streets_config(osm_config):
    """Test der Straßen-Konfiguration."""
    streets_config = osm_config['osm']['streets']
    
    # Überprüfe erforderliche Straßen-Einstellungen
    required_settings = ['tags', 'filters', 'defaults']
    for setting in required_settings:
        assert setting in streets_config
    
    # Überprüfe Straßentypen
    assert 'street_types' in streets_config
    street_types = streets_config['street_types']
    assert isinstance(street_types, dict)
    assert all(isinstance(value, bool) for value in street_types.values())

def test_config_validation(osm_config):
    """Test der Konfigurationsvalidierung."""
    # Überprüfe BBOX-Format
    bbox = osm_config['osm']['bbox']
    assert len(bbox) == 4
    assert all(isinstance(x, (int, float)) for x in bbox)
    
    # Überprüfe Cache-Einstellungen
    cache = osm_config['osm']['cache']
    assert 'enabled' in cache
    assert 'directory' in cache
    assert isinstance(cache['enabled'], bool)
    assert isinstance(cache['directory'], str)

def test_config_consistency(osm_config):
    """Test der Konfigurationskonsistenz."""
    # Überprüfe, ob die Filter konsistent sind
    buildings_filters = osm_config['osm']['buildings']['filters']
    streets_filters = osm_config['osm']['streets']['filters']
    
    # Überprüfe, ob die Filter nicht widersprüchlich sind
    for key in buildings_filters:
        if key in streets_filters:
            assert buildings_filters[key] != streets_filters[key], \
                f"Widersprüchliche Filter für Gebäude und Straßen gefunden: {key}" 
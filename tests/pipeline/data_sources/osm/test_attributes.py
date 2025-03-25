"""
Tests für den OSM-Attributprozessor.
"""

import pytest
from pipeline.data_sources.osm.attributes import OSMAttributeProcessor

@pytest.fixture
def test_config():
    """Fixture für eine Test-Konfiguration."""
    return {
        'buildings': {
            'defaults': {
                'height': 10,
                'floors': 3,
                'category': 'residential'
            }
        }
    }

@pytest.fixture
def attribute_processor(test_config):
    """Fixture für den Attributprozessor."""
    return OSMAttributeProcessor(test_config)

@pytest.fixture
def valid_building():
    """Fixture für ein gültiges Gebäude mit Attributen."""
    return {
        'name': 'Test Building',
        'height': '15.5',
        'building:levels': '4',
        'building': 'apartments',
        'addr:street': 'Test Street',
        'addr:housenumber': '42'
    }

@pytest.fixture
def valid_street():
    """Fixture für eine gültige Straße mit Attributen."""
    return {
        'name': 'Test Street',
        'width': '12.5',
        'lanes': '2',
        'surface': 'asphalt',
        'highway': 'residential'
    }

def test_process_building_attributes(attribute_processor, valid_building):
    """Test der Gebäudeattributverarbeitung."""
    attributes = attribute_processor.process_building_attributes(valid_building)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['Name'] == 'Test Building'
    assert attributes['height_ag'] == 15.5
    assert attributes['floors_ag'] == 4
    assert attributes['category'] == 'apartments'

def test_process_building_attributes_with_address(attribute_processor, valid_building):
    """Test der Gebäudeattributverarbeitung mit Adresse."""
    del valid_building['name']  # Entferne Namen, um Adressverarbeitung zu testen
    attributes = attribute_processor.process_building_attributes(valid_building)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['Name'] == 'Test Street 42'

def test_process_building_attributes_minimal(attribute_processor):
    """Test der Gebäudeattributverarbeitung mit minimalen Daten."""
    minimal_building = {'building': 'yes'}
    attributes = attribute_processor.process_building_attributes(minimal_building)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['category'] == 'yes'

def test_process_street_attributes(attribute_processor, valid_street):
    """Test der Straßenattributverarbeitung."""
    attributes = attribute_processor.process_street_attributes(valid_street)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['Name'] == 'Test Street'
    assert attributes['width'] == 12.5
    assert attributes['lanes'] == 2
    assert attributes['surface'] == 'asphalt'
    assert attributes['highway'] == 'residential'

def test_process_street_attributes_minimal(attribute_processor):
    """Test der Straßenattributverarbeitung mit minimalen Daten."""
    minimal_street = {'highway': 'residential'}
    attributes = attribute_processor.process_street_attributes(minimal_street)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['highway'] == 'residential'

def test_process_street_attributes_with_list(attribute_processor):
    """Test der Straßenattributverarbeitung mit Listen-Werten."""
    street_with_list = {
        'highway': ['residential', 'service'],
        'name': 'Test Street'
    }
    attributes = attribute_processor.process_street_attributes(street_with_list)
    
    assert attributes['data_source'] == 'osm'
    assert attributes['highway'] == 'residential'  # Sollte ersten Wert nehmen 
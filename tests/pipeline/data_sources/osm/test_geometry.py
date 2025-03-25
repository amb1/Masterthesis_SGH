"""
Tests für den OSM-Geometrieprozessor.
"""

import pytest
from shapely.geometry import Polygon, LineString, Point
from pipeline.data_sources.osm.geometry import OSMGeometryProcessor

@pytest.fixture
def geometry_processor():
    """Fixture für den Geometrieprozessor."""
    return OSMGeometryProcessor()

@pytest.fixture
def valid_building():
    """Fixture für ein gültiges Gebäude."""
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    return {'geometry': polygon}

@pytest.fixture
def valid_street():
    """Fixture für eine gültige Straße."""
    line = LineString([(0, 0), (1, 1)])
    return {'geometry': line}

def test_process_building_geometry(geometry_processor, valid_building):
    """Test der Gebäudegeometrieverarbeitung."""
    geometry = geometry_processor.process_building_geometry(valid_building)
    assert isinstance(geometry, Polygon)
    assert geometry.is_valid
    assert geometry.area > 0

def test_process_invalid_building_geometry(geometry_processor):
    """Test mit ungültiger Gebäudegeometrie."""
    invalid_building = {'geometry': Point(0, 0)}  # Point statt Polygon
    geometry = geometry_processor.process_building_geometry(invalid_building)
    assert geometry is None

def test_process_street_geometry(geometry_processor, valid_street):
    """Test der Straßengeometrieverarbeitung."""
    geometry = geometry_processor.process_street_geometry(valid_street)
    assert isinstance(geometry, LineString)
    assert geometry.is_valid
    assert geometry.length > 0

def test_process_invalid_street_geometry(geometry_processor):
    """Test mit ungültiger Straßengeometrie."""
    invalid_street = {'geometry': Point(0, 0)}  # Point statt LineString
    geometry = geometry_processor.process_street_geometry(invalid_street)
    assert geometry is None

def test_validate_building_geometry(geometry_processor, valid_building):
    """Test der Gebäudegeometrievalidierung."""
    geometry = valid_building['geometry']
    assert geometry_processor.validate_building_geometry(geometry)

def test_validate_street_geometry(geometry_processor, valid_street):
    """Test der Straßengeometrievalidierung."""
    geometry = valid_street['geometry']
    assert geometry_processor.validate_street_geometry(geometry) 
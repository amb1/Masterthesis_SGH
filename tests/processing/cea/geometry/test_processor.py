"""
Tests für den CEA-Geometrie-Prozessor.
"""
import pytest
import numpy as np
from shapely.geometry import Polygon
from pipeline.processing.cea.geometry.processor import CEAGeometryProcessor

@pytest.fixture
def config():
    return {
        'default_building_height': 12.0
    }

@pytest.fixture
def processor(config):
    return CEAGeometryProcessor(config)

@pytest.fixture
def sample_geometry():
    return {
        'type': 'Polygon',
        'coordinates': [
            [
                [0, 0, 0],
                [0, 10, 0],
                [10, 10, 3],
                [10, 0, 3],
                [0, 0, 0]
            ]
        ]
    }

def test_validate_valid_geometry(processor, sample_geometry):
    assert processor.validate(sample_geometry) is True

def test_validate_invalid_geometry(processor):
    invalid_geometry = {'type': 'Polygon'}  # Fehlende Koordinaten
    assert processor.validate(invalid_geometry) is False

def test_create_polygon(processor, sample_geometry):
    polygon = processor._create_polygon(sample_geometry)
    assert isinstance(polygon, Polygon)
    assert polygon.area == 100.0  # 10x10 Rechteck

def test_calculate_area(processor, sample_geometry):
    polygon = processor._create_polygon(sample_geometry)
    area = processor._calculate_area(polygon)
    assert area == pytest.approx(100.0)

def test_calculate_perimeter(processor, sample_geometry):
    polygon = processor._create_polygon(sample_geometry)
    perimeter = processor._calculate_perimeter(polygon)
    assert perimeter == pytest.approx(40.0)  # 4 Seiten à 10 Einheiten

def test_calculate_height_from_coordinates(processor, sample_geometry):
    height = processor._calculate_height(sample_geometry)
    assert height == pytest.approx(3.0)  # Max Z (3) - Min Z (0)

def test_calculate_height_from_attribute(processor):
    geometry = {'height': '15.5', 'type': 'Polygon', 'coordinates': []}
    height = processor._calculate_height(geometry)
    assert height == pytest.approx(15.5)

def test_calculate_height_fallback(processor):
    geometry = {'type': 'Polygon', 'coordinates': [[[0, 0], [1, 1]]]}
    height = processor._calculate_height(geometry)
    assert height == pytest.approx(12.0)  # Fallback aus config

def test_calculate_footprint(processor, sample_geometry):
    polygon = processor._create_polygon(sample_geometry)
    footprint = processor._calculate_footprint(polygon)
    
    assert footprint['min_x'] == pytest.approx(0.0)
    assert footprint['min_y'] == pytest.approx(0.0)
    assert footprint['max_x'] == pytest.approx(10.0)
    assert footprint['max_y'] == pytest.approx(10.0)
    assert footprint['width'] == pytest.approx(10.0)
    assert footprint['length'] == pytest.approx(10.0)

def test_calculate_orientation(processor):
    # Rechteck mit 45° Rotation
    coords = [
        [0, 0],
        [-1, 1],
        [1, 3],
        [3, 1],
        [0, 0]
    ]
    geometry = {'type': 'Polygon', 'coordinates': [coords]}
    polygon = processor._create_polygon(geometry)
    orientation = processor._calculate_orientation(polygon)
    assert orientation == pytest.approx(45.0, abs=1.0)

def test_process_complete(processor, sample_geometry):
    result = processor.process(sample_geometry)
    
    assert result['type'] == 'Polygon'
    assert result['area'] == pytest.approx(100.0)
    assert result['perimeter'] == pytest.approx(40.0)
    assert result['height'] == pytest.approx(3.0)
    assert isinstance(result['footprint'], dict)
    assert isinstance(result['orientation'], float) 
"""
Tests für die Transformationsfunktionen
"""
import pytest
from pipeline.processing.transformations import (
    map_building_type,
    map_construction_period,
    shorten_id,
    transform_value
)

@pytest.fixture
def sample_building_data():
    """Testdaten für Gebäude-Transformationen."""
    return {
        "type": "residential",
        "year": 1985,
        "id": "way/123456789",
        "height": "12.5"
    }

def test_building_type_mapping():
    """Test die Gebäudetyp-Transformation."""
    assert map_building_type("residential") == "RESIDENTIAL"
    assert map_building_type("commercial") == "OFFICE"
    assert map_building_type("industrial") == "INDUSTRIAL"
    assert map_building_type("unknown") == "MIXED"

def test_construction_period_mapping():
    """Test die Bauperioden-Transformation."""
    assert map_construction_period(1985) == "1980-1989"
    assert map_construction_period(2020) == "2020-2029"
    assert map_construction_period(1800) == "PRE-1900"

def test_id_shortening():
    """Test die ID-Kürzung."""
    assert shorten_id("way/123456789") == "w123456789"
    assert shorten_id("node/987654321") == "n987654321"
    assert shorten_id("relation/12345") == "r12345"

def test_value_transformation():
    """Test die Werte-Transformation."""
    assert transform_value("12.5", float) == 12.5
    assert transform_value("", float, default=0.0) == 0.0
    with pytest.raises(ValueError):
        transform_value("invalid", float)

def test_building_transformation_pipeline(sample_building_data):
    """Test die vollständige Transformations-Pipeline."""
    transformed = {
        "type": map_building_type(sample_building_data["type"]),
        "period": map_construction_period(sample_building_data["year"]),
        "id": shorten_id(sample_building_data["id"]),
        "height": transform_value(sample_building_data["height"], float)
    }
    
    assert transformed == {
        "type": "RESIDENTIAL",
        "period": "1980-1989",
        "id": "w123456789",
        "height": 12.5
    } 
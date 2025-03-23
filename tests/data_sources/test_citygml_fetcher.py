"""
Unit-Tests für den CityGML Fetcher.
"""

import pytest
from pathlib import Path
import geopandas as gpd
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings

@pytest.fixture
def test_config():
    return {
        "citygml": {
            "input_file": "tests/data/test.gml",
            "filters": {
                "building_types": ["Residential", "Office"],
                "min_height": 3.0
            }
        }
    }

@pytest.fixture
def test_output_dir(tmp_path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return str(output_dir)

def test_fetch_citygml_buildings_success(test_config, test_output_dir):
    """Test erfolgreicher Datenabruf."""
    # Arrange
    citygml_file = "tests/data/test.gml"
    
    # Act
    result = fetch_citygml_buildings(
        citygml_file=citygml_file,
        output_dir=test_output_dir,
        config=test_config["citygml"]
    )
    
    # Assert
    assert result is not None
    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) > 0
    assert "geometry" in result.columns
    assert "height" in result.columns
    assert "building_type" in result.columns

def test_fetch_citygml_buildings_invalid_file(test_config, test_output_dir):
    """Test mit ungültiger Eingabedatei."""
    # Arrange
    citygml_file = "nicht_vorhanden.gml"
    
    # Act & Assert
    with pytest.raises(FileNotFoundError):
        fetch_citygml_buildings(
            citygml_file=citygml_file,
            output_dir=test_output_dir,
            config=test_config["citygml"]
        )

def test_fetch_citygml_buildings_invalid_output_dir(test_config):
    """Test mit ungültigem Ausgabeverzeichnis."""
    # Arrange
    citygml_file = "tests/data/test.gml"
    output_dir = "/ungueltig/nicht/vorhanden"
    
    # Act & Assert
    with pytest.raises(Exception):
        fetch_citygml_buildings(
            citygml_file=citygml_file,
            output_dir=output_dir,
            config=test_config["citygml"]
        )

def test_fetch_citygml_buildings_empty_config(test_output_dir):
    """Test mit leerer Konfiguration."""
    # Arrange
    citygml_file = "tests/data/test.gml"
    
    # Act & Assert
    with pytest.raises(KeyError):
        fetch_citygml_buildings(
            citygml_file=citygml_file,
            output_dir=test_output_dir,
            config={}
        ) 
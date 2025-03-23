"""
Unit-Tests für den CityGML-Prozessor.
"""

import unittest
import pytest
from pathlib import Path
import xml.etree.ElementTree as ET
from unittest.mock import Mock, patch
from shapely.geometry import Polygon

from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor

@pytest.fixture
def sample_citygml():
    """Erstellt ein Beispiel-CityGML-Dokument."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<CityModel 
    xmlns="http://www.opengis.net/citygml/2.0"
    xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
    xmlns:gml="http://www.opengis.net/gml">
    <cityObjectMember>
        <bldg:Building>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>0 0 0 1 0 0 1 1 0 0 1 0</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:CompositeSurface>
                    </gml:exterior>
                </gml:Solid>
            </bldg:lod2Solid>
        </bldg:Building>
    </cityObjectMember>
</CityModel>"""

@pytest.fixture
def citygml_file(tmp_path, sample_citygml):
    """Erstellt eine temporäre CityGML-Datei."""
    file_path = tmp_path / "test.gml"
    file_path.write_text(sample_citygml)
    return file_path

@pytest.fixture
def processor():
    """Erstellt eine CityGMLProcessor-Instanz."""
    return CityGMLProcessor()

def test_extract_building_footprint(processor, citygml_file):
    """Test extract_building_footprint mit Beispieldaten."""
    tree = ET.parse(citygml_file)
    building = tree.find(".//{http://www.opengis.net/citygml/building/2.0}Building")
    
    footprint = processor.extract_building_footprint(building)
    assert footprint is not None
    assert isinstance(footprint, Polygon)
    assert not footprint.is_empty

def test_extract_solid_geometry(processor, citygml_file):
    """Test _extract_solid_geometry mit Beispieldaten."""
    tree = ET.parse(citygml_file)
    solid = tree.find(".//{http://www.opengis.net/gml}Solid")
    ns = {"gml": "http://www.opengis.net/gml"}
    
    geometry = processor._extract_solid_geometry(solid, ns)
    assert geometry is not None
    assert isinstance(geometry, Polygon)
    assert not geometry.is_empty

def test_extract_multisurface_geometry(processor, citygml_file):
    """Test _extract_multisurface_geometry mit Beispieldaten."""
    tree = ET.parse(citygml_file)
    multisurface = tree.find(".//{http://www.opengis.net/gml}CompositeSurface")
    ns = {"gml": "http://www.opengis.net/gml"}
    
    geometry = processor._extract_multisurface_geometry(multisurface, ns)
    assert geometry is not None
    assert isinstance(geometry, Polygon)
    assert not geometry.is_empty

def test_extract_coordinates(processor, citygml_file):
    """Test _extract_coordinates mit Beispieldaten."""
    tree = ET.parse(citygml_file)
    polygon = tree.find(".//{http://www.opengis.net/gml}Polygon")
    ns = {"gml": "http://www.opengis.net/gml"}
    
    coordinates = processor._extract_coordinates(polygon, ns)
    assert coordinates is not None
    assert len(coordinates) > 0
    assert all(len(coord) == 2 for coord in coordinates)  # x, y Koordinaten

@patch('web.supabase.scripts.supabase_citygml_processor.CityGMLProcessor.get_wfs_data')
def test_process_citygml(mock_get_wfs, processor, citygml_file):
    """Test process_citygml mit gemockten WFS-Daten."""
    mock_get_wfs.return_value = {
        'properties': {
            'year_built': 2000,
            'building_type': 'residential'
        }
    }
    
    result = processor.process_citygml(str(citygml_file))
    assert result is not None
    assert isinstance(result, list)

@patch('web.supabase.scripts.supabase_citygml_processor.CityGMLProcessor.convert_to_3dtiles')
def test_convert_to_3dtiles(mock_convert, processor, citygml_file):
    """Test convert_to_3dtiles mit gemockter Konvertierung."""
    mock_convert.return_value = True
    
    result = processor.convert_to_3dtiles(str(citygml_file))
    assert result is True
    mock_convert.assert_called_once_with(str(citygml_file))

def test_generate_cea_input(processor):
    """Test generate_cea_input mit Beispielgebäude."""
    building = {
        'properties': {
            'year_built': 2000,
            'building_type': 'residential',
            'height': 10.0
        },
        'geometry': {
            'coordinates': [[[0, 0], [1, 0], [1, 1], [0, 1]]]
        }
    }
    
    cea_input = processor.generate_cea_input(building)
    assert cea_input is not None
    assert cea_input['zone_type'] == 'residential'
    assert cea_input['use_type'] == 'EFH' 
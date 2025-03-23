"""
Tests für den CityGML-Konverter
"""
import pytest
from pathlib import Path
import xml.etree.ElementTree as ET
from ...converters.citygml import CityGMLConverter

@pytest.fixture
def sample_citygml(tmp_path):
    """Erstellt eine Test-CityGML-Datei"""
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <CityModel xmlns:gml="http://www.opengis.net/gml"
               xmlns:bldg="http://www.opengis.net/citygml/building/1.0">
        <gml:Envelope srsName="EPSG:31256">
            <gml:lowerCorner>0 0 0</gml:lowerCorner>
            <gml:upperCorner>100 100 30</gml:upperCorner>
        </gml:Envelope>
        <bldg:Building gml:id="BUILDING_1">
            <bldg:measuredHeight>25.5</bldg:measuredHeight>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>
                                                0 0 0 10 0 0 10 10 0 0 10 0 0 0 0
                                            </gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:CompositeSurface>
                    </gml:exterior>
                </gml:Solid>
            </bldg:lod2Solid>
        </bldg:Building>
    </CityModel>
    """
    file_path = tmp_path / "test.gml"
    file_path.write_text(content)
    return file_path

@pytest.fixture
def converter():
    """Erstellt eine Instanz des CityGML-Konverters"""
    return CityGMLConverter()

def test_converter_initialization(converter):
    """Test der Konverter-Initialisierung"""
    assert converter.namespaces['gml'] == 'http://www.opengis.net/gml'
    assert converter.namespaces['bldg'] == 'http://www.opengis.net/citygml/building/1.0'
    assert converter.namespaces['gen'] == 'http://www.opengis.net/citygml/generics/2.0'

def test_convert_nonexistent_file(converter, tmp_path):
    """Test der Konvertierung einer nicht existierenden Datei"""
    input_path = tmp_path / "nonexistent.gml"
    output_path = tmp_path / "output"
    assert not converter.convert(input_path, output_path)

def test_convert_valid_file(converter, sample_citygml, tmp_path):
    """Test der Konvertierung einer gültigen CityGML-Datei"""
    output_path = tmp_path / "output"
    assert converter.convert(sample_citygml, output_path)
    
    # Überprüfe Ausgabedateien
    assert (output_path / "tileset.json").exists()
    assert (output_path / "tile.b3dm").exists()

def test_extract_building_geometry(converter, sample_citygml):
    """Test der Geometrie-Extraktion"""
    tree = ET.parse(str(sample_citygml))
    root = tree.getroot()
    building = root.find('.//bldg:Building', converter.namespaces)
    
    geometries = converter._extract_building_geometry(building)
    assert geometries is not None
    assert len(geometries) > 0
    
    # Überprüfe Koordinaten
    coords = geometries[0]
    assert len(coords) == 5  # 5 Punkte für das Grundpolygon
    assert all(len(point) == 3 for point in coords)  # 3D-Koordinaten

def test_extract_polygon_coordinates(converter, sample_citygml):
    """Test der Koordinaten-Extraktion"""
    tree = ET.parse(str(sample_citygml))
    root = tree.getroot()
    polygon = root.find('.//gml:Polygon', converter.namespaces)
    
    coords = converter._extract_polygon_coordinates(polygon)
    assert coords is not None
    assert len(coords) == 5  # 5 Punkte
    assert all(len(point) == 3 for point in coords)  # 3D-Koordinaten
    
    # Überprüfe spezifische Koordinaten
    assert coords[0] == [0, 0, 0]  # Erster Punkt
    assert coords[2] == [10, 10, 0]  # Dritter Punkt

def test_convert_invalid_geometry(converter, tmp_path):
    """Test der Konvertierung mit ungültiger Geometrie"""
    # Erstelle CityGML ohne Geometrie
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <CityModel xmlns:gml="http://www.opengis.net/gml"
               xmlns:bldg="http://www.opengis.net/citygml/building/1.0">
        <bldg:Building gml:id="BUILDING_1">
            <bldg:measuredHeight>25.5</bldg:measuredHeight>
        </bldg:Building>
    </CityModel>
    """
    input_path = tmp_path / "invalid.gml"
    input_path.write_text(content)
    output_path = tmp_path / "output"
    
    assert not converter.convert(input_path, output_path) 
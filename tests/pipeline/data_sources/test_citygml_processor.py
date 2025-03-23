"""
Tests für den CityGML-Prozessor
"""
import pytest
from pathlib import Path
import yaml
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor
from lxml import etree

@pytest.fixture
def test_config():
    """Erstellt eine Test-Konfiguration"""
    return {
        'citygml': {
            'namespaces': {
                'gml': "http://www.opengis.net/gml",
                'bldg': "http://www.opengis.net/citygml/building/1.0",
                'gen': 'http://www.opengis.net/citygml/generics/1.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            }
        },
        'input': {
            'directory': "input",
            'file_pattern': "*.gml",
            'encoding': "utf-8"
        },
        'processing': {
            'crs': {
                'input': "EPSG:25832",
                'output': "EPSG:4326"
            },
            'lod_level': 2,
            'validation': {
                'check_geometry': True,
                'fix_invalid': True
            }
        },
        'output': {
            'formats': [
                {
                    'type': "3dtiles",
                    'directory': "output/3dtiles",
                    'options': {
                        'geometric_error': 10.0,
                        'refinement': "REPLACE"
                    }
                },
                {
                    'type': "geojson",
                    'directory': "output/geojson",
                    'options': {
                        'simplify_tolerance': 0.1,
                        'include_height': True
                    }
                }
            ]
        }
    }

@pytest.fixture
def sample_citygml(tmp_path):
    """Erstellt eine Test-CityGML-Datei"""
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <CityModel xmlns:gml="http://www.opengis.net/gml"
               xmlns:bldg="http://www.opengis.net/citygml/building/1.0">
        <gml:boundedBy>
            <gml:Envelope srsName="EPSG:25832">
                <gml:lowerCorner>385761.59 5819928.01</gml:lowerCorner>
                <gml:upperCorner>385780.52 5819947.47</gml:upperCorner>
            </gml:Envelope>
        </gml:boundedBy>
        <cityObjectMember>
            <bldg:Building gml:id="BLDG_0001">
                <bldg:measuredHeight>12.5</bldg:measuredHeight>
                <bldg:storeysAboveGround>4</bldg:storeysAboveGround>
                <bldg:lod2Solid>
                    <gml:Solid>
                        <gml:exterior>
                            <gml:CompositeSurface>
                                <gml:surfaceMember>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>
                                                    385761.59 5819928.01 0
                                                    385780.52 5819928.01 0
                                                    385780.52 5819947.47 0
                                                    385761.59 5819947.47 0
                                                    385761.59 5819928.01 0
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
        </cityObjectMember>
    </CityModel>
    """
    
    file_path = tmp_path / "input/test.gml"
    file_path.write_text(content)
    return str(file_path)

@pytest.fixture
def processor(test_config):
    """Erstellt eine Instanz des CityGML-Prozessors"""
    return CityGMLBuildingProcessor(test_config)

@pytest.fixture
def sample_building_xml():
    """Beispiel-XML für ein Gebäude mit verschiedenen Attributen."""
    return """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   xmlns:gen="http://www.opengis.net/citygml/generics/1.0"
                   xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0">
        <bldg:measuredHeight>10.5</bldg:measuredHeight>
        <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
        <bldg:function>residential</bldg:function>
        <bldg:yearOfConstruction>1990</bldg:yearOfConstruction>
        <bldg:address>
            <xAL:AddressDetails>
                <xAL:ThoroughfareName>Teststraße</xAL:ThoroughfareName>
                <xAL:BuildingNumber>42</xAL:BuildingNumber>
                <xAL:PostalCode>1234</xAL:PostalCode>
                <xAL:LocalityName>Teststadt</xAL:LocalityName>
                <xAL:CountryName>Österreich</xAL:CountryName>
            </xAL:AddressDetails>
        </bldg:address>
        <gen:stringAttribute name="owner">
            <gen:value>Max Mustermann</gen:value>
        </gen:stringAttribute>
        <gen:intAttribute name="renovationYear">
            <gen:value>2010</gen:value>
        </gen:intAttribute>
        <gen:doubleAttribute name="energyRating">
            <gen:value>2.5</gen:value>
        </gen:doubleAttribute>
    </bldg:Building>
    """

def test_processor_initialization(processor, test_config):
    """Test der Prozessor-Initialisierung"""
    assert processor.config is not None
    assert Path(processor.config['input']['directory']).exists()
    assert Path(processor.config['output']['formats'][0]['directory']).exists()

def test_load_citygml(processor, sample_citygml):
    """Test des Ladens einer CityGML-Datei"""
    gdf = processor.load_citygml(sample_citygml)
    
    assert isinstance(gdf, gpd.GeoDataFrame)
    assert len(gdf) == 1
    assert gdf.crs.to_string() == "EPSG:25832"
    assert all(col in gdf.columns for col in ['geometry', 'building_id', 'height', 'storeys'])
    
    # Überprüfe Attributwerte
    assert gdf.iloc[0]['building_id'] == "BLDG_0001"
    assert gdf.iloc[0]['height'] == 12.5
    assert gdf.iloc[0]['storeys'] == 4
    
    # Überprüfe Geometrie
    geom = gdf.iloc[0]['geometry']
    assert isinstance(geom, Polygon)
    assert geom.is_valid

def test_transform_crs(processor, sample_citygml):
    """Test der CRS-Transformation"""
    gdf = processor.load_citygml(sample_citygml)
    gdf_transformed = processor.transform_crs(gdf)
    
    assert gdf_transformed.crs.to_string() == "EPSG:4326"
    assert gdf_transformed.geometry.is_valid.all()

def test_validate_geometries(processor, sample_citygml):
    """Test der Geometrie-Validierung"""
    gdf = processor.load_citygml(sample_citygml)
    valid_gdf = processor.validate_geometries(gdf)
    
    assert valid_gdf.geometry.is_valid.all()
    assert len(valid_gdf) == len(gdf)

def test_export_3dtiles(processor, sample_citygml):
    """Test des 3D Tiles Exports"""
    gdf = processor.load_citygml(sample_citygml)
    output_path = Path(processor.config['output']['formats'][0]['directory'])
    
    processor.export_3dtiles(gdf, output_path)
    
    assert (output_path / "tileset.json").exists()
    assert list(output_path.glob("*.b3dm"))  # Prüfe auf B3DM-Dateien

def test_export_geojson(processor, sample_citygml):
    """Test des GeoJSON Exports"""
    gdf = processor.load_citygml(sample_citygml)
    output_path = Path(processor.config['output']['formats'][1]['directory'])
    
    processor.export_geojson(gdf, output_path / "buildings.geojson")
    
    assert (output_path / "buildings.geojson").exists()
    exported_gdf = gpd.read_file(output_path / "buildings.geojson")
    assert len(exported_gdf) == len(gdf)
    assert all(col in exported_gdf.columns for col in ['building_id', 'height', 'storeys'])

def test_process_file(processor, sample_citygml):
    """Test der Gesamtverarbeitung einer Datei"""
    success = processor.process_file(sample_citygml)
    assert success
    
    # Überprüfe Ausgabedateien
    assert list(Path(processor.config['output']['formats'][0]['directory']).glob("*.b3dm"))
    assert list(Path(processor.config['output']['formats'][1]['directory']).glob("*.geojson"))

def test_invalid_file(processor, tmp_path):
    """Test mit ungültiger Eingabedatei"""
    invalid_file = tmp_path / "input/invalid.gml"
    invalid_file.write_text("Invalid content")
    
    success = processor.process_file(str(invalid_file))
    assert not success

def test_missing_file(processor):
    """Test mit nicht existierender Datei"""
    success = processor.process_file("nonexistent.gml")
    assert not success

def test_extract_generic_attributes_basic(processor, sample_building_xml):
    """Test der grundlegenden Attributextraktion."""
    building = etree.fromstring(sample_building_xml)
    attributes = processor._extract_generic_attributes(building)
    
    # Teste CityGML-spezifische Attribute
    assert attributes['measuredHeight'] == 10.5
    assert attributes['storeysAboveGround'] == 3
    assert attributes['function'] == 'residential'
    assert attributes['yearOfConstruction'] == 1990
    
    # Teste Adressattribute
    assert attributes['street'] == 'Teststraße'
    assert attributes['houseNumber'] == '42'
    assert attributes['postalCode'] == '1234'
    assert attributes['city'] == 'Teststadt'
    assert attributes['country'] == 'Österreich'
    
    # Teste generische Attribute
    assert attributes['owner'] == 'Max Mustermann'
    assert attributes['renovationYear'] == 2010
    assert attributes['energyRating'] == 2.5

def test_extract_generic_attributes_missing_values(processor):
    """Test der Attributextraktion mit fehlenden Werten."""
    xml = """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   xmlns:gen="http://www.opengis.net/citygml/generics/1.0">
        <bldg:measuredHeight></bldg:measuredHeight>
        <bldg:function>unknown</bldg:function>
        <gen:stringAttribute name="emptyValue">
            <gen:value></gen:value>
        </gen:stringAttribute>
    </bldg:Building>
    """
    building = etree.fromstring(xml)
    attributes = processor._extract_generic_attributes(building)
    
    assert 'measuredHeight' not in attributes
    assert attributes['function'] == 'unknown'
    assert 'emptyValue' not in attributes

def test_extract_generic_attributes_invalid_values(processor):
    """Test der Attributextraktion mit ungültigen Werten."""
    xml = """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   xmlns:gen="http://www.opengis.net/citygml/generics/1.0">
        <bldg:measuredHeight>invalid</bldg:measuredHeight>
        <bldg:storeysAboveGround>3.5</bldg:storeysAboveGround>
        <gen:intAttribute name="invalidInt">
            <gen:value>not a number</gen:value>
        </gen:intAttribute>
    </bldg:Building>
    """
    building = etree.fromstring(xml)
    attributes = processor._extract_generic_attributes(building)
    
    assert 'measuredHeight' not in attributes
    assert attributes['storeysAboveGround'] == 3
    assert 'invalidInt' not in attributes

def test_extract_generic_attributes_alternative_paths(processor):
    """Test der Attributextraktion mit alternativen XPath-Ausdrücken."""
    xml = """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml">
        <bldg:height>10.5</bldg:height>
        <bldg:numberOfFloorsAboveGround>3</bldg:numberOfFloorsAboveGround>
        <bldg:buildingFunction>residential</bldg:buildingFunction>
        <bldg:constructionYear>1990</bldg:constructionYear>
    </bldg:Building>
    """
    building = etree.fromstring(xml)
    attributes = processor._extract_generic_attributes(building)
    
    assert attributes['measuredHeight'] == 10.5
    assert attributes['storeysAboveGround'] == 3
    assert attributes['function'] == 'residential'
    assert attributes['yearOfConstruction'] == 1990 
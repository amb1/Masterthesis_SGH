"""Tests für den CityGML Building Processor."""

import os
import pytest
from pathlib import Path
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor

# Fixture-Pfade
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CITYGML_FIXTURES = FIXTURES_DIR / "citygml"

@pytest.fixture(scope="session", autouse=True)
def setup_fixtures():
    """Erstellt die Fixture-Verzeichnisse falls nicht vorhanden."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    CITYGML_FIXTURES.mkdir(exist_ok=True)
    return FIXTURES_DIR

@pytest.fixture
def test_config():
    """Basis-Testkonfiguration."""
    return {
        'citygml': {
            'namespaces': {
                'bldg': 'http://www.opengis.net/citygml/building/1.0',
                'gml': 'http://www.opengis.net/gml',
                'gen': 'http://www.opengis.net/citygml/generics/1.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            }
        },
        'processing': {
            'crs': {
                'input': 'EPSG:31256',
                'output': 'EPSG:4326'
            },
            'validation': {
                'check_geometry': True,
                'fix_invalid': True
            }
        },
        'output': {
            'formats': [
                {
                    'type': 'geojson',
                    'directory': 'geojson',
                    'options': {
                        'simplify_tolerance': 0.1
                    }
                },
                {
                    'type': '3dtiles',
                    'directory': '3dtiles',
                    'options': {}
                }
            ]
        }
    }

@pytest.fixture
def processor(test_config):
    """CityGML Processor Instanz."""
    return CityGMLBuildingProcessor(test_config)

@pytest.fixture
def sample_building_xml():
    """Beispiel-XML für ein Gebäude mit verschiedenen Attributen."""
    return """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   xmlns:gen="http://www.opengis.net/citygml/generics/1.0"
                   xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
                   gml:id="BLDG_00001">
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
        <bldg:lod2Solid>
            <gml:Solid>
                <gml:exterior>
                    <gml:CompositeSurface>
                        <gml:surfaceMember>
                            <gml:Polygon>
                                <gml:exterior>
                                    <gml:LinearRing>
                                        <gml:posList>0 0 0 10 0 0 10 10 0 0 10 0 0 0 0</gml:posList>
                                    </gml:LinearRing>
                                </gml:exterior>
                            </gml:Polygon>
                        </gml:surfaceMember>
                    </gml:CompositeSurface>
                </gml:exterior>
            </gml:Solid>
        </bldg:lod2Solid>
    </bldg:Building>
    """

@pytest.fixture
def test_file_path():
    """Pfad zur Test-CityGML-Datei."""
    return CITYGML_FIXTURES / "test_building.gml"

def test_extract_generic_attributes_basic(processor, sample_building_xml):
    """Test der grundlegenden Attributextraktion."""
    building = etree.fromstring(sample_building_xml)
    attributes = processor._extract_generic_attributes(building)
    
    # CityGML-spezifische Attribute
    assert attributes['measuredHeight'] == 10.5
    assert attributes['storeysAboveGround'] == 3
    assert attributes['function'] == 'residential'
    assert attributes['yearOfConstruction'] == 1990
    
    # Adressattribute
    assert attributes['street'] == 'Teststraße'
    assert attributes['houseNumber'] == '42'
    assert attributes['postalCode'] == '1234'
    assert attributes['city'] == 'Teststadt'
    assert attributes['country'] == 'Österreich'
    
    # Generische Attribute
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

def test_extract_geometry_solid(processor, sample_building_xml):
    """Test der Geometrieextraktion aus einem Solid."""
    building = etree.fromstring(sample_building_xml)
    geometry = processor._extract_geometry(building)
    
    assert isinstance(geometry, Polygon)
    assert geometry.is_valid
    assert len(list(geometry.exterior.coords)) == 5

def test_extract_geometry_multisurface(processor):
    """Test der Geometrieextraktion aus einer MultiSurface."""
    xml = """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml">
        <bldg:lod2MultiSurface>
            <gml:MultiSurface>
                <gml:surfaceMember>
                    <gml:Polygon>
                        <gml:exterior>
                            <gml:LinearRing>
                                <gml:coordinates>0,0 10,0 10,10 0,10 0,0</gml:coordinates>
                            </gml:LinearRing>
                        </gml:exterior>
                    </gml:Polygon>
                </gml:surfaceMember>
            </gml:MultiSurface>
        </bldg:lod2MultiSurface>
    </bldg:Building>
    """
    building = etree.fromstring(xml)
    geometry = processor._extract_geometry(building)
    
    assert isinstance(geometry, Polygon)
    assert geometry.is_valid
    assert len(list(geometry.exterior.coords)) == 5

def test_process_building_with_parts(processor):
    """Test der Verarbeitung eines Gebäudes mit BuildingParts."""
    xml = """
    <bldg:Building xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   gml:id="BLDG_00002">
        <bldg:measuredHeight>15.0</bldg:measuredHeight>
        <bldg:lod2Solid>
            <gml:Solid>
                <gml:exterior>
                    <gml:CompositeSurface>
                        <gml:surfaceMember>
                            <gml:Polygon>
                                <gml:exterior>
                                    <gml:LinearRing>
                                        <gml:posList>0 0 0 5 0 0 5 5 0 0 5 0 0 0 0</gml:posList>
                                    </gml:LinearRing>
                                </gml:exterior>
                            </gml:Polygon>
                        </gml:surfaceMember>
                    </gml:CompositeSurface>
                </gml:exterior>
            </gml:Solid>
        </bldg:lod2Solid>
        <bldg:BuildingPart>
            <bldg:measuredHeight>10.0</bldg:measuredHeight>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:posList>5 0 0 10 0 0 10 5 0 5 5 0 5 0 0</gml:posList>
                                        </gml:LinearRing>
                                    </gml:exterior>
                                </gml:Polygon>
                            </gml:surfaceMember>
                        </gml:CompositeSurface>
                    </gml:exterior>
                </gml:Solid>
            </bldg:lod2Solid>
        </bldg:BuildingPart>
    </bldg:Building>
    """
    building = etree.fromstring(xml)
    building_data = processor._process_building(building)
    
    assert building_data['gml_id'] == 'BLDG_00002'
    assert building_data['has_building_parts']
    assert building_data['building_parts_count'] == 1
    assert building_data['part_measuredHeight_avg'] == 10.0
    assert isinstance(building_data['geometry'], Polygon)
    assert building_data['geometry'].is_valid 

def test_process_file(processor, test_file_path):
    """Test der vollständigen Dateiverarbeitung."""
    success = processor.process_file(str(test_file_path))
    assert success
    
    # Prüfe ob Ausgabeverzeichnisse erstellt wurden
    for format_config in processor.output_formats:
        output_dir = Path(format_config.get('directory', ''))
        if not output_dir.is_absolute():
            output_dir = get_output_path("citygml") / output_dir
        assert output_dir.exists()

def test_extract_buildings_from_file(processor, test_file_path):
    """Test der Gebäudeextraktion aus einer Datei."""
    buildings_gdf = processor.extract_buildings(str(test_file_path))
    
    assert buildings_gdf is not None
    assert len(buildings_gdf) == 2
    assert buildings_gdf.crs == "EPSG:31256"
    
    # Prüfe erstes Gebäude
    building1 = buildings_gdf[buildings_gdf['gml_id'] == 'BLDG_00001'].iloc[0]
    assert building1['measuredHeight'] == 10.5
    assert building1['storeysAboveGround'] == 3
    assert building1['function'] == 'residential'
    assert building1['yearOfConstruction'] == 1990
    assert building1['owner'] == 'Max Mustermann'
    assert building1['renovationYear'] == 2010
    assert building1['energyRating'] == 2.5
    assert isinstance(building1['geometry'], Polygon)
    
    # Prüfe zweites Gebäude
    building2 = buildings_gdf[buildings_gdf['gml_id'] == 'BLDG_00002'].iloc[0]
    assert building2['measuredHeight'] == 15.0
    assert building2['function'] == 'commercial'
    assert building2['has_building_parts']
    assert building2['building_parts_count'] == 1
    assert building2['part_measuredHeight_avg'] == 10.0
    assert isinstance(building2['geometry'], Polygon)

def test_transform_crs(processor):
    """Test der CRS-Transformation."""
    # Erstelle Test-GeoDataFrame
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs="EPSG:31256")
    
    # Transformiere CRS
    transformed_gdf = processor.transform_crs(gdf)
    assert transformed_gdf.crs == "EPSG:4326"

def test_validate_geometries(processor):
    """Test der Geometrie-Validierung."""
    # Erstelle Test-GeoDataFrame mit ungültiger Geometrie
    invalid_geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (2, 2), (0, 0)])
    gdf = gpd.GeoDataFrame({'geometry': [invalid_geometry]})
    
    # Validiere Geometrien
    validated_gdf = processor.validate_geometries(gdf)
    assert all(validated_gdf.geometry.is_valid)

def test_export_geojson(processor, tmp_path):
    """Test des GeoJSON-Exports."""
    # Erstelle Test-GeoDataFrame
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame({
        'geometry': [geometry],
        'attribute': ['test']
    }, crs="EPSG:4326")
    
    # Exportiere als GeoJSON
    output_path = tmp_path / "test.geojson"
    processor.export_geojson(gdf, output_path, {'simplify_tolerance': 0.1})
    
    assert output_path.exists()
    exported_gdf = gpd.read_file(output_path)
    assert len(exported_gdf) == 1
    assert exported_gdf.crs == "EPSG:4326"

def test_process_file_with_invalid_input(processor):
    """Test der Fehlerbehandlung bei ungültiger Eingabe."""
    success = processor.process_file("nonexistent.gml")
    assert not success

def test_extract_buildings_with_invalid_xml(processor, tmp_path):
    """Test der Fehlerbehandlung bei ungültigem XML."""
    # Erstelle ungültige XML-Datei
    invalid_file = tmp_path / "invalid.gml"
    invalid_file.write_text("<invalid>xml</invalid>")
    
    buildings_gdf = processor.extract_buildings(str(invalid_file))
    assert buildings_gdf is None 
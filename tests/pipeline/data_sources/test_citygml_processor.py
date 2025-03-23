"""Tests für den CityGML Building Processor."""

import os
import pytest
from pathlib import Path
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor
from core.project_paths import get_output_path, get_config_path

@pytest.fixture(scope="session")
def citygml_fixtures_dir(test_fixtures_dir):
    """CityGML Testdaten-Verzeichnis."""
    fixtures_dir = test_fixtures_dir / "citygml"
    fixtures_dir.mkdir(exist_ok=True)
    return fixtures_dir

@pytest.fixture
def test_config(global_config):
    """Testkonfiguration für CityGML Tests."""
    return {
        'citygml': global_config.get('citygml', {
            'namespaces': {
                'bldg': 'http://www.opengis.net/citygml/building/1.0',
                'gml': 'http://www.opengis.net/gml',
                'gen': 'http://www.opengis.net/citygml/generics/1.0',
                'xAL': 'urn:oasis:names:tc:ciq:xsdschema:xAL:2.0'
            }
        }),
        'processing': global_config.get('processing', {
            'crs': {
                'input': 'EPSG:31256',
                'output': 'EPSG:4326'
            },
            'validation': {
                'check_geometry': True,
                'fix_invalid': True
            }
        }),
        'output': global_config.get('output', {
            'formats': [
                {
                    'type': 'geojson',
                    'directory': str(get_output_path('citygml') / 'geojson'),
                    'options': {
                        'simplify_tolerance': 0.1
                    }
                },
                {
                    'type': '3dtiles',
                    'directory': str(get_output_path('citygml') / '3dtiles'),
                    'options': {}
                }
            ]
        })
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
def test_file_path(citygml_fixtures_dir):
    """Erstellt eine Test-CityGML-Datei."""
    test_file = citygml_fixtures_dir / "test_building.gml"
    if not test_file.exists():
        test_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
        <CityModel xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                   xmlns:gml="http://www.opengis.net/gml"
                   xmlns:gen="http://www.opengis.net/citygml/generics/1.0"
                   xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0">
            <gml:boundedBy>
                <gml:Envelope srsName="EPSG:31256">
                    <gml:lowerCorner>0 0</gml:lowerCorner>
                    <gml:upperCorner>100 100</gml:upperCorner>
                </gml:Envelope>
            </gml:boundedBy>
            <cityObjectMember>
                <bldg:Building gml:id="BLDG_00001">
                    <bldg:measuredHeight>10.5</bldg:measuredHeight>
                    <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
                    <bldg:function>residential</bldg:function>
                    <bldg:yearOfConstruction>1990</bldg:yearOfConstruction>
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
            </cityObjectMember>
        </CityModel>
        """)
    return test_file

def test_process_file(processor, test_file_path):
    """Test der vollständigen Dateiverarbeitung."""
    success = processor.process_file(str(test_file_path))
    assert success
    
    # Prüfe ob Ausgabeverzeichnisse erstellt wurden
    for format_config in processor.output_formats:
        output_dir = Path(format_config.get('directory', ''))
        assert output_dir.exists()

def test_extract_buildings_from_file(processor, test_file_path):
    """Test der Gebäudeextraktion aus einer Datei."""
    buildings_gdf = processor.extract_buildings(str(test_file_path))
    
    assert buildings_gdf is not None
    assert len(buildings_gdf) == 1
    assert buildings_gdf.crs == "EPSG:31256"
    
    # Prüfe Gebäudeattribute
    building = buildings_gdf.iloc[0]
    assert building['measuredHeight'] == 10.5
    assert building['storeysAboveGround'] == 3
    assert building['function'] == 'residential'
    assert building['yearOfConstruction'] == 1990
    assert isinstance(building['geometry'], Polygon)

def test_transform_crs(processor):
    """Test der CRS-Transformation."""
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame({'geometry': [geometry]}, crs="EPSG:31256")
    
    transformed_gdf = processor.transform_crs(gdf)
    assert transformed_gdf.crs == "EPSG:4326"

def test_validate_geometries(processor):
    """Test der Geometrie-Validierung."""
    invalid_geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (2, 2), (0, 0)])
    gdf = gpd.GeoDataFrame({'geometry': [invalid_geometry]})
    
    validated_gdf = processor.validate_geometries(gdf)
    assert all(validated_gdf.geometry.is_valid)

def test_export_geojson(processor, tmp_path):
    """Test des GeoJSON-Exports."""
    geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    gdf = gpd.GeoDataFrame({
        'geometry': [geometry],
        'attribute': ['test']
    }, crs="EPSG:4326")
    
    output_path = tmp_path / "test.geojson"
    processor.export_geojson(gdf, output_path, {'simplify_tolerance': 0.1})
    
    assert output_path.exists()
    exported_gdf = gpd.read_file(output_path)
    assert len(exported_gdf) == 1
    assert exported_gdf.crs == "EPSG:4326" 
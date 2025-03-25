"""
Tests für die CEA-Datenverarbeitung und Gebäudeanalyse.

Diese Tests validieren die Verarbeitung von CityGML-Daten gemäß den Regeln
aus base/092-cea-mapping.
"""

import os
import pytest
from pathlib import Path
from lxml import etree
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
from pipeline.processing.cea_processor import CEABuildingProcessor
from pipeline.processing.cea_mapper import CEAMapper
from core.config_manager import get_module_config

@pytest.fixture
def sample_citygml():
    """Erstellt ein Beispiel-CityGML-Gebäude."""
    return """
    <?xml version="1.0" encoding="UTF-8"?>
    <CityModel xmlns="http://www.opengis.net/citygml/2.0"
               xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
               xmlns:gml="http://www.opengis.net/gml"
               xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0">
        <cityObjectMember>
            <bldg:Building gml:id="BUILDING_1">
                <bldg:function>1000</bldg:function>
                <bldg:yearOfConstruction>1960</bldg:yearOfConstruction>
                <bldg:measuredHeight>12.0</bldg:measuredHeight>
                <bldg:storeysAboveGround>4</bldg:storeysAboveGround>
                <bldg:storeysBelowGround>1</bldg:storeysBelowGround>
                <bldg:address>
                    <Address>
                        <xAL:ThoroughfareName>Teststraße</xAL:ThoroughfareName>
                        <xAL:ThoroughfareNumber>42</xAL:ThoroughfareNumber>
                        <xAL:PostalCodeNumber>1010</xAL:PostalCodeNumber>
                    </Address>
                </bldg:address>
            </bldg:Building>
        </cityObjectMember>
    </CityModel>
    """

@pytest.fixture
def sample_config():
    """Erstellt eine Beispiel-Konfiguration."""
    return {
        'cea': {
            'required_fields': [
                'Name', 'REFERENCE', 'YEAR', 'USE_TYPE',
                'floors_ag', 'floors_bg', 'height_ag', 'height_bg'
            ],
            'validation': {
                'geometry': {
                    'min_area': 10,
                    'max_area': 10000
                },
                'floors_ag': {
                    'min': 1,
                    'max': 50
                },
                'floors_bg': {
                    'min': 0,
                    'max': 10
                },
                'height_ag': {
                    'min': 2.5,
                    'max': 150
                },
                'height_bg': {
                    'min': 0,
                    'max': 30
                },
                'YEAR': {
                    'min': 1800,
                    'max': 2100
                }
            },
            'geometry': {
                'floor_height': 3.0
            },
            'defaults': {
                'floors_ag': 4,
                'floors_bg': 1,
                'height_ag': 12.0,
                'height_bg': 3.0,
                'YEAR': 1960,
                'USE_TYPE': 'RESIDENTIAL'
            }
        }
    }

@pytest.fixture
def processor(sample_config):
    """Erstellt eine Instanz des CEA-Prozessors."""
    return CEABuildingProcessor(sample_config)

@pytest.fixture
def mapper(sample_config):
    """Erstellt eine Instanz des CEA-Mappers."""
    return CEAMapper(sample_config['cea'])

def test_citygml_basic_processing(processor, sample_citygml):
    """Test: Grundlegende Verarbeitung von CityGML-Daten."""
    # Parse CityGML
    root = etree.fromstring(sample_citygml.encode())
    building = root.xpath("//bldg:Building", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"})[0]
    
    # Erstelle Testdaten
    test_data = {
        'citygml': {
            'buildings': [building]
        }
    }
    
    # Verarbeite Daten
    result = processor.process_buildings(test_data)
    
    # Validiere Ergebnisse
    assert result
    assert 'buildings' in result
    buildings_gdf = result['buildings']
    assert not buildings_gdf.empty
    
    # Prüfe gemappte Felder
    building_data = buildings_gdf.iloc[0]
    assert building_data['Name'] == 'Teststraße_42'
    assert building_data['REFERENCE'] == 'BUILDING_1'
    assert building_data['YEAR'] == 1960
    assert building_data['USE_TYPE'] == 'RESIDENTIAL'
    assert building_data['floors_ag'] == 4
    assert building_data['floors_bg'] == 1
    assert building_data['height_ag'] == 12.0
    assert building_data['height_bg'] == 3.0

def test_citygml_validation(processor, sample_citygml):
    """Test: Validierung von CityGML-Daten."""
    # Parse CityGML
    root = etree.fromstring(sample_citygml.encode())
    building = root.xpath("//bldg:Building", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"})[0]
    
    # Erstelle ungültige Testdaten
    invalid_building = building
    invalid_building.find(".//bldg:storeysAboveGround", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"}).text = "100"
    
    test_data = {
        'citygml': {
            'buildings': [invalid_building]
        }
    }
    
    # Verarbeite Daten
    result = processor.process_buildings(test_data)
    
    # Validiere Ergebnisse
    assert not result, "Verarbeitung sollte fehlschlagen bei ungültigen Daten"

def test_field_mapping(mapper, sample_citygml):
    """Test: Mapping von CityGML-Feldern."""
    # Parse CityGML
    root = etree.fromstring(sample_citygml.encode())
    building = root.xpath("//bldg:Building", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"})[0]
    
    # Teste Name-Mapping
    name = mapper.map_field('Name', building, 'citygml')
    assert name == 'Teststraße_42'
    
    # Teste REFERENCE-Mapping
    reference = mapper.map_field('REFERENCE', building, 'citygml')
    assert reference == 'BUILDING_1'
    
    # Teste YEAR-Mapping
    year = mapper.map_field('YEAR', building, 'citygml')
    assert year == 1960
    
    # Teste USE_TYPE-Mapping
    use_type = mapper.map_field('USE_TYPE', building, 'citygml')
    assert use_type == 'RESIDENTIAL'

def test_geometry_validation(processor):
    """Test: Validierung von Gebäudegeometrien."""
    # Erstelle gültige Geometrie
    valid_polygon = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])
    valid_data = gpd.GeoDataFrame({
        'geometry': [valid_polygon],
        'Name': ['Test'],
        'REFERENCE': ['REF1'],
        'YEAR': [1960],
        'USE_TYPE': ['RESIDENTIAL'],
        'floors_ag': [4],
        'floors_bg': [1],
        'height_ag': [12.0],
        'height_bg': [3.0]
    })
    
    # Validiere gültige Geometrie
    assert processor.validate_geometries(valid_data)
    
    # Erstelle ungültige Geometrie (zu klein)
    invalid_polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
    invalid_data = valid_data.copy()
    invalid_data.geometry = [invalid_polygon]
    
    # Validiere ungültige Geometrie
    assert not processor.validate_geometries(invalid_data)

def test_building_attributes(processor, sample_citygml):
    """Test: Validierung von Gebäudeattributen."""
    # Parse CityGML
    root = etree.fromstring(sample_citygml.encode())
    building = root.xpath("//bldg:Building", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"})[0]
    
    # Erstelle Testdaten
    test_data = {
        'citygml': {
            'buildings': [building]
        }
    }
    
    # Verarbeite Daten
    result = processor.process_buildings(test_data)
    
    # Validiere Attribute
    assert result
    buildings_gdf = result['buildings']
    building_data = buildings_gdf.iloc[0]
    
    # Prüfe Pflichtfelder
    required_fields = processor.cea_config['required_fields']
    for field in required_fields:
        assert field in building_data
        assert building_data[field] is not None
    
    # Prüfe Wertebereich
    validation_rules = processor.cea_config['validation']
    for field, rules in validation_rules.items():
        if field in building_data:
            if 'min' in rules:
                assert building_data[field] >= rules['min']
            if 'max' in rules:
                assert building_data[field] <= rules['max']

def test_metadata_creation(processor, sample_citygml):
    """Test: Erstellung von Metadaten."""
    # Parse CityGML
    root = etree.fromstring(sample_citygml.encode())
    building = root.xpath("//bldg:Building", 
                         namespaces={"bldg": "http://www.opengis.net/citygml/building/1.0"})[0]
    
    # Erstelle Testdaten
    test_data = {
        'citygml': {
            'buildings': [building]
        }
    }
    
    # Verarbeite Daten
    result = processor.process_buildings(test_data)
    
    # Validiere Metadaten
    assert result
    assert 'metadata' in result
    metadata = result['metadata']
    
    # Prüfe Metadatenfelder
    assert 'building_count' in metadata
    assert metadata['building_count'] == 1
    assert 'total_floor_area' in metadata
    assert 'total_footprint_area' in metadata
    assert 'building_types' in metadata
    assert 'construction_years' in metadata
    
    # Prüfe Baujahre
    years = metadata['construction_years']
    assert years['min'] == 1960
    assert years['max'] == 1960
    assert years['mean'] == 1960 
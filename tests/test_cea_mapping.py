"""
Tests für die CEA-Mapping Funktionalität.
"""
import pytest
from lxml import etree
from pipeline.processing.cea_mapper import CEAMapper

def test_name_mapping_citygml(cea_mapping_config, sample_citygml_building):
    """Test für das Mapping des Namens aus CityGML-Daten."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    name = mapper.map_field("Name", citygml_data=xml)
    assert name == "Teststraße_42"

def test_name_mapping_wfs(cea_mapping_config, sample_wfs_building):
    """Test für das Mapping des Namens aus WFS-Daten."""
    mapper = CEAMapper(cea_mapping_config)
    name = mapper.map_field("Name", wfs_data=sample_wfs_building)
    assert name == "Teststraße_42"

def test_building_attributes_citygml(cea_mapping_config, sample_citygml_building):
    """Test für das Mapping von Gebäudeattributen aus CityGML."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    height = mapper.map_field("height_ag", citygml_data=xml)
    floors = mapper.map_field("floors_ag", citygml_data=xml)
    assert height == 15.5
    assert floors == 4

def test_building_attributes_wfs(cea_mapping_config, sample_wfs_building):
    """Test für das Mapping von Gebäudeattributen aus WFS."""
    mapper = CEAMapper(cea_mapping_config)
    height = mapper.map_field("height_ag", wfs_data=sample_wfs_building)
    floors = mapper.map_field("floors_ag", wfs_data=sample_wfs_building)
    assert height == 15.5
    assert floors == 4

def test_use_type_mapping(cea_mapping_config, sample_wfs_building):
    """Test für das Mapping von Nutzungstypen."""
    mapper = CEAMapper(cea_mapping_config)
    use_type = mapper.map_field("1ST_USE", wfs_data=sample_wfs_building)
    assert use_type == "RESIDENTIAL"

def test_fallback_values(cea_mapping_config):
    """Test für Fallback-Werte bei fehlenden Daten."""
    mapper = CEAMapper(cea_mapping_config)
    floors_bg = mapper.map_field("floors_bg", wfs_data={})
    assert floors_bg == 1  # Default-Wert

def test_address_fields_citygml(cea_mapping_config, sample_citygml_building):
    """Test für das Mapping von Adressfeldern aus CityGML."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    street = mapper.map_field("street", citygml_data=xml)
    house_no = mapper.map_field("house_no", citygml_data=xml)
    postcode = mapper.map_field("postcode", citygml_data=xml)
    assert street == "Teststraße"
    assert house_no == "42"
    assert postcode == "1010"

def test_address_fields_wfs(cea_mapping_config, sample_wfs_building):
    """Test für das Mapping von Adressfeldern aus WFS."""
    mapper = CEAMapper(cea_mapping_config)
    street = mapper.map_field("street", wfs_data=sample_wfs_building)
    house_no = mapper.map_field("house_no", wfs_data=sample_wfs_building)
    postcode = mapper.map_field("postcode", wfs_data=sample_wfs_building)
    assert street == "Teststraße"
    assert house_no == "42"
    assert postcode == "1010"

def test_multiple_use_types_wfs(cea_mapping_config, sample_wfs_building):
    """Test für das Mapping von mehreren Nutzungstypen."""
    mapper = CEAMapper(cea_mapping_config)
    first_use = mapper.map_field("1ST_USE", wfs_data=sample_wfs_building)
    second_use = mapper.map_field("2ND_USE", wfs_data=sample_wfs_building)
    third_use = mapper.map_field("3RD_USE", wfs_data=sample_wfs_building)
    assert first_use == "RESIDENTIAL"
    assert second_use == "OFFICE"
    assert third_use == "RETAIL"

def test_extended_address_fields_citygml(cea_mapping_config, sample_citygml_building):
    """Test für das Mapping von erweiterten Adressfeldern aus CityGML."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    city = xml.xpath(".//xAL:LocalityName/text()", namespaces=mapper.namespaces)
    country = xml.xpath(".//xAL:CountryName/text()", namespaces=mapper.namespaces)
    assert city[0] == "Wien"
    assert country[0] == "Österreich"

def test_validation_rules(cea_mapping_config):
    """Test für die Validierung von Gebäudeparametern."""
    mapper = CEAMapper(cea_mapping_config)
    with pytest.raises(ValueError):
        mapper.validate_field("floors_ag", None)  # Required field

def test_combined_name_reference(cea_mapping_config, sample_citygml_building):
    """Test für die Kombination von Name und Referenz aus CityGML."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    name = mapper.map_field("Name", citygml_data=xml)
    reference = mapper.map_field("REFERENCE", citygml_data=xml)
    assert name == "Teststraße_42"
    assert reference == "BUILDING_1234"

def test_source_priority(cea_mapping_config, sample_citygml_building, sample_wfs_building):
    """Test für die Priorisierung von Datenquellen."""
    mapper = CEAMapper(cea_mapping_config)
    xml = etree.fromstring(sample_citygml_building)
    
    # CityGML sollte Vorrang vor WFS haben
    height_citygml = mapper.map_field("height_ag", citygml_data=xml, wfs_data=sample_wfs_building)
    assert height_citygml == 15.5  # CityGML-Wert 
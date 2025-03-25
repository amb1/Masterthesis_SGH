"""
Tests für die CEA-Verarbeitung von CityGML-Daten.
"""
import os
from pathlib import Path
import pytest
from lxml import etree
from pipeline.processing.cea_mapper import CEAMapper
from pipeline.processing.cea_processor import CEABuildingProcessor

@pytest.fixture
def test_citygml_file():
    """Fixture für die Test-CityGML-Datei."""
    return Path("data/raw/citygml/099082.gml")

@pytest.fixture
def cea_processor(cea_mapping_config):
    """Fixture für den CEA-Prozessor."""
    config = {
        'paths': {
            'input': {
                'format': 'citygml',
                'files': {
                    'citygml': 'data/raw/citygml/099082.gml'
                }
            }
        },
        'cea': cea_mapping_config
    }
    return CEABuildingProcessor(config)

def test_citygml_file_exists(test_citygml_file):
    """Test ob die CityGML-Datei existiert."""
    assert test_citygml_file.exists(), f"CityGML-Datei nicht gefunden: {test_citygml_file}"

def test_citygml_basic_processing(cea_processor, test_citygml_file):
    """Test für die grundlegende Verarbeitung der CityGML-Datei."""
    # Lade die CityGML-Datei
    with open(test_citygml_file, 'rb') as f:
        citygml_data = f.read()
    
    # Parse die XML-Daten
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(citygml_data, parser=parser)
    
    # Debug: Zeige die verfügbaren Namespaces
    print("\nVerfügbare Namespaces:")
    for ns in root.nsmap.items():
        print(f"{ns[0]}: {ns[1]}")
    
    # Definiere die Namespaces
    namespaces = {
        'gml': 'http://www.opengis.net/gml',
        'bldg': 'http://www.opengis.net/citygml/building/2.0',
        'core': 'http://www.opengis.net/citygml/2.0',
        'gen': 'http://www.opengis.net/citygml/generics/2.0'
    }
    
    # Versuche verschiedene XPath-Ausdrücke
    xpath_expressions = [
        "//bldg:Building",
        "//Building",
        "//*[local-name()='Building']",
        "//core:cityObjectMember/bldg:Building"
    ]
    
    buildings = []
    for xpath in xpath_expressions:
        try:
            result = root.xpath(xpath, namespaces=namespaces)
            if result:
                print(f"\nGebäude gefunden mit XPath: {xpath}")
                print(f"Anzahl gefundener Gebäude: {len(result)}")
                buildings = result
                break
        except Exception as e:
            print(f"\nFehler bei XPath '{xpath}': {str(e)}")
    
    assert len(buildings) > 0, "Keine Gebäude in der CityGML-Datei gefunden"
    
    # Teste die Verarbeitung des ersten Gebäudes
    building = buildings[0]
    
    # Debug: Zeige die Struktur des ersten Gebäudes
    print("\nStruktur des ersten Gebäudes:")
    print(etree.tostring(building, pretty_print=True).decode())
    
    processed_data = cea_processor.process_building(building)
    
    # Überprüfe die wichtigsten Attribute
    assert 'Name' in processed_data, "Name nicht in verarbeiteten Daten"
    assert 'height_ag' in processed_data, "Höhe nicht in verarbeiteten Daten"
    assert 'floors_ag' in processed_data, "Geschosse nicht in verarbeiteten Daten"
    assert 'REFERENCE' in processed_data, "Referenz nicht in verarbeiteten Daten" 
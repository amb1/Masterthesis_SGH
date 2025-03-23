"""
Tests für die Transformations-Funktionen
"""
import pytest
from pathlib import Path
from utils.transformations import (
    get_period_suffix,
    map_building_use,
    get_standard_prefix,
    combine_building_standard,
    shorten_id,
    transform_value
)

@pytest.fixture
def test_config_path(tmp_path):
    """Erstellt eine Test-Konfigurationsdatei"""
    config_content = """
building_types:
  use_type:
    wohngebäude: MULTI_RES
    geschäftshaus: RETAIL
    industriegebäude: INDUSTRIAL
    bürogebäude: OFFICE
  standard_prefix:
    wohngebäude: MFH
    geschäftshaus: SCR
    industriegebäude: IND
    bürogebäude: OFB
"""
    config_file = tmp_path / "test_config.yml"
    config_file.write_text(config_content)
    return str(config_file)

def test_get_period_suffix():
    """Test der Periodensuffix-Bestimmung"""
    test_cases = [
        (1850, "_A"),  # Vor 1859
        (1900, "_B"),  # 1860-1918
        (1930, "_C"),  # 1919-1948
        (1950, "_D"),  # 1949-1957
        (1960, "_E"),  # 1958-1968
        (1970, "_F"),  # 1969-1978
        (1980, "_G"),  # 1979-1983
        (1990, "_H"),  # 1984-1994
        (2000, "_I"),  # 1995-2001
        (2005, "_J"),  # 2002-2009
        (2010, "_K"),  # 2010-2015
        (2020, "_L")   # Nach 2015
    ]
    
    for year, expected in test_cases:
        assert get_period_suffix(year) == expected, f"Fehler bei Jahr {year}"

def test_map_building_use(test_config_path):
    """Test des Gebäudetyp-Mappings"""
    # Test mit Konfigurationsdatei
    assert map_building_use("wohngebäude", test_config_path) == "MULTI_RES"
    assert map_building_use("geschäftshaus", test_config_path) == "RETAIL"
    
    # Test der Fallback-Logik
    assert map_building_use("Einkaufszentrum") == "RETAIL"
    assert map_building_use("Industriehalle") == "INDUSTRIAL"
    assert map_building_use("Bürokomplex") == "OFFICE"
    assert map_building_use("Hotel") == "HOTEL"
    assert map_building_use("Krankenhaus") == "HOSPITAL"
    assert map_building_use("Villa") == "SINGLE_RES"
    assert map_building_use("Unbekannt") == "MULTI_RES"  # Standard-Fallback

def test_get_standard_prefix(test_config_path):
    """Test der STANDARD-Prefix-Bestimmung"""
    # Test mit Konfigurationsdatei
    assert get_standard_prefix("wohngebäude", test_config_path) == "MFH"
    assert get_standard_prefix("geschäftshaus", test_config_path) == "SCR"
    
    # Test der Fallback-Logik
    assert get_standard_prefix("Einkaufszentrum") == "SCR"
    assert get_standard_prefix("Industriehalle") == "IND"
    assert get_standard_prefix("Bürokomplex") == "OFB"
    assert get_standard_prefix("Hotel") == "HOT"
    assert get_standard_prefix("Krankenhaus") == "HOS"
    assert get_standard_prefix("Villa") == "SFH"
    assert get_standard_prefix("Unbekannt") == "MFH"  # Standard-Fallback

def test_combine_building_standard(test_config_path):
    """Test der Kombination von Gebäudetyp und Periode"""
    # Test verschiedener Kombinationen
    assert combine_building_standard("wohngebäude", 1900, test_config_path) == "MFH_B"
    assert combine_building_standard("geschäftshaus", 1950, test_config_path) == "SCR_D"
    assert combine_building_standard("Unbekannt", 2000) == "MFH_I"
    
    # Test mit ungültigen Werten
    assert combine_building_standard("", 1900) == "MFH_B"
    assert combine_building_standard(None, 2000) == "MFH_I"

def test_shorten_id():
    """Test der ID-Kürzung"""
    # Test mit verschiedenen Längen
    long_id = "sehr_langer_identifier_12345"
    assert len(shorten_id(long_id)) == 10  # Standard-Länge
    assert len(shorten_id(long_id, 5)) == 5  # Benutzerdefinierte Länge
    
    # Test der Konsistenz
    assert shorten_id(long_id) == shorten_id(long_id)  # Gleiche Eingabe = gleiche Ausgabe
    assert shorten_id("") == ""  # Leere Eingabe
    assert shorten_id(None) == ""  # None-Eingabe

def test_transform_value():
    """Test der Werttransformation"""
    # Test der ID-Kürzung
    config = {
        'function': 'shorten_id',
        'max_length': 5
    }
    assert len(transform_value("langer_wert", config)) == 5
    
    # Test ohne Transformation
    assert transform_value("test", {}) == "test"
    assert transform_value(123, {}) == 123
    
    # Test mit ungültiger Transformation
    config_invalid = {
        'function': 'unknown_function'
    }
    assert transform_value("test", config_invalid) == "test" 
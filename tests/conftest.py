"""
Gemeinsame Test-Fixtures und Konfiguration.
"""
import pytest
import os
import sys
import yaml
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon
from core.config_manager import load_config
from core.project_paths import get_config_path, get_output_path

# Füge das Projekt-Root-Verzeichnis zum Python-Pfad hinzu
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture(autouse=True)
def setup_test_env():
    """Richtet die Test-Umgebung ein."""
    # Setze Umgebungsvariablen für Tests
    os.environ["TESTING"] = "true"
    yield
    # Cleanup nach den Tests
    if "TESTING" in os.environ:
        del os.environ["TESTING"]

@pytest.fixture(scope="session")
def test_data_dir():
    """Fixture für den Testdaten-Ordner"""
    return Path(__file__).parent / "test_data"

@pytest.fixture(scope="session")
def test_fixtures_dir():
    """Basis-Verzeichnis für Test-Fixtures."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture(scope="session")
def test_outputs_dir():
    """Basis-Verzeichnis für Test-Ausgaben."""
    return Path(__file__).parent / "outputs"

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(test_data_dir, test_fixtures_dir, test_outputs_dir):
    """Richtet die Testumgebung ein."""
    # Erstelle Verzeichnisse
    for directory in [test_data_dir, test_fixtures_dir, test_outputs_dir]:
        directory.mkdir(exist_ok=True)
        
    # Erstelle Unterverzeichnisse für verschiedene Datenquellen
    (test_fixtures_dir / "citygml").mkdir(exist_ok=True)
    (test_fixtures_dir / "osm").mkdir(exist_ok=True)
    (test_fixtures_dir / "wfs").mkdir(exist_ok=True)
    
    # Erstelle Ausgabeverzeichnisse
    (test_outputs_dir / "citygml").mkdir(exist_ok=True)
    (test_outputs_dir / "osm").mkdir(exist_ok=True)
    (test_outputs_dir / "3dtiles").mkdir(exist_ok=True)
    (test_outputs_dir / "geojson").mkdir(exist_ok=True)

@pytest.fixture
def global_config():
    """Lädt die globale Testkonfiguration."""
    config_path = get_config_path() / "global.yml"
    return load_config(config_path)

@pytest.fixture
def citygml_config(global_config):
    """CityGML-spezifische Konfiguration."""
    return global_config.get('citygml', {})

@pytest.fixture
def osm_config(global_config):
    """OSM-spezifische Konfiguration."""
    return global_config.get('osm', {})

@pytest.fixture
def wfs_config(global_config):
    """WFS-spezifische Konfiguration."""
    return global_config.get('wfs', {})

@pytest.fixture
def sample_site_gdf():
    """Erstellt ein Beispiel-Site-Polygon für Tests."""
    # Erstelle ein einfaches Polygon
    polygon = Polygon([(0, 0), (0, 100), (100, 100), (100, 0), (0, 0)])
    return gpd.GeoDataFrame(geometry=[polygon], crs="EPSG:31256")

@pytest.fixture
def sample_buildings_gdf():
    """Erstellt Beispiel-Gebäude für Tests."""
    # Erstelle einige Beispiel-Gebäude
    buildings = [
        Polygon([(0, 0), (0, 20), (20, 20), (20, 0), (0, 0)]),
        Polygon([(30, 30), (30, 50), (50, 50), (50, 30), (30, 30)]),
        Polygon([(60, 60), (60, 80), (80, 80), (80, 60), (60, 60)])
    ]
    return gpd.GeoDataFrame(geometry=buildings, crs="EPSG:31256")

@pytest.fixture
def sample_osm_config():
    """Erstellt eine Beispiel-OSM-Konfiguration für Tests."""
    return {
        'buildings': {
            'buffer_distance': 100,
            'defaults': {
                'height': 10,
                'floors': 3,
                'year': 1990,
                'category': 'residential',
                'REFERENCE': ''
            }
        }
    }

@pytest.fixture
def sample_street_config():
    """Erstellt eine Beispiel-Straßen-Konfiguration für Tests."""
    return {
        'street_types': {
            'primary': True,
            'secondary': True,
            'tertiary': True,
            'residential': True
        },
        'network_type': 'all',
        'buffer_distance': 100
    }

@pytest.fixture
def sample_global_config():
    """Erstellt eine Beispiel-Global-Konfiguration für Tests."""
    return {
        'paths': {
            'outputs': {
                'buildings': 'outputs/buildings',
                'geometry': 'outputs/geometry',
                'networks': 'outputs/networks'
            }
        },
        'processing': {
            'site_polygon': {
                'buffer_distance': 3
            }
        }
    }

@pytest.fixture(scope="session")
def cea_mapping_config():
    """Lädt die CEA-Mapping Konfiguration."""
    config_path = Path(__file__).parent.parent / "base/053-interfaces/cea_mapping.yml"
    with open(config_path, "r", encoding="utf-8") as f:
        # Lade alle YAML-Dokumente und kombiniere sie
        docs = list(yaml.safe_load_all(f))
        # Kombiniere die Dokumente, wobei das zweite Dokument Vorrang hat
        combined_config = {}
        for doc in docs:
            if doc:  # Überspringe leere Dokumente
                combined_config.update(doc)
        return combined_config

@pytest.fixture
def sample_citygml_building():
    """Beispiel CityGML-Gebäudedaten für Tests."""
    return """<Building xmlns="http://www.opengis.net/citygml/building/2.0"
         xmlns:gml="http://www.opengis.net/gml"
         xmlns:xAL="urn:oasis:names:tc:ciq:xsdschema:xAL:2.0"
         xmlns:bldg="http://www.opengis.net/citygml/building/2.0"
         gml:id="BUILDING_1234">
    <bldg:measuredHeight>15.5</bldg:measuredHeight>
    <bldg:storeysAboveGround>4</bldg:storeysAboveGround>
    <bldg:function>1000</bldg:function>
    <bldg:address>
        <Address>
            <xAL:AddressDetails>
                <xAL:Country>
                    <xAL:CountryName>Österreich</xAL:CountryName>
                    <xAL:Locality Type="City">
                        <xAL:LocalityName>Wien</xAL:LocalityName>
                        <xAL:Thoroughfare Type="Street">
                            <xAL:ThoroughfareName>Teststraße</xAL:ThoroughfareName>
                            <xAL:ThoroughfareNumber>42</xAL:ThoroughfareNumber>
                        </xAL:Thoroughfare>
                        <xAL:PostalCode>
                            <xAL:PostalCodeNumber>1010</xAL:PostalCodeNumber>
                        </xAL:PostalCode>
                    </xAL:Locality>
                </xAL:Country>
            </xAL:AddressDetails>
        </Address>
    </bldg:address>
</Building>"""

@pytest.fixture
def sample_wfs_building():
    """Beispiel WFS-Gebäudedaten für Tests."""
    return {
        "OBJECTID": "4711",
        "Gebäudeinfo_STRNAML": "Teststraße",
        "Gebäudeinfo_VONN": "42",
        "Gebäudeinfo_BEZ": "1010",
        "Gebäudeinfo_L_NUTZUNG": "W2.1.-Bürgerhaus-kleine Haustypen ohne Hof",
        "Gebäudeinfo_L_NUTZUNG2": "6.-Bauten der öffentlichen und privaten Wirtschaft",
        "Gebäudeinfo_L_NUTZUNG3": "10.-Kaufhäuser",
        "Gebäudeinfo_NUTZER": "Privat",
        "Gebäudeinfo_NUTZER2": "Firma",
        "Gebäudeinfo_NUTZER3": "Handel",
        "HoeheDach": "15.5",
        "GEBAEUDEINFOOGD_GESCH_ANZ": "4",
        "Gebäudeinfo_NS": "1",
        "Gebäudeinfo_BAUJAHR": "1890",
        "Gebäudeinfo_L_BAUTYP": "STANDARD",
        "Gebäudeinfo_HA_NAME": "Testhaus"
    }

@pytest.fixture
def sample_validation_config():
    """Fixture für Validierungskonfiguration"""
    return {
        "validation": {
            "height_ag": {
                "min": 2.0,
                "max": 200.0
            },
            "floors_ag": {
                "min": 1,
                "max": 100
            },
            "year_built": {
                "min": 1800,
                "max": 2024
            }
        }
    } 
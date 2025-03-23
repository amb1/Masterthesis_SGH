"""
Fixtures für CityGML-bezogene Tests.

Dieses Modul enthält wiederverwendbare Fixtures für Tests der CityGML-Verarbeitung.
"""

import pytest
from pathlib import Path
import xml.etree.ElementTree as ET

@pytest.fixture
def sample_citygml_content():
    """Erstellt einen Beispiel-CityGML-Inhalt für Tests."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<CityModel xmlns="http://www.opengis.net/citygml/2.0">
    <cityObjectMember>
        <bldg:Building gml:id="B001">
            <bldg:function>1000</bldg:function>
            <bldg:yearOfConstruction>1910</bldg:yearOfConstruction>
            <bldg:measuredHeight uom="m">10.0</bldg:measuredHeight>
            <bldg:storeysAboveGround>3</bldg:storeysAboveGround>
            <bldg:lod2Solid>
                <gml:Solid>
                    <gml:exterior>
                        <gml:CompositeSurface>
                            <gml:surfaceMember>
                                <gml:Polygon>
                                    <gml:exterior>
                                        <gml:LinearRing>
                                            <gml:pos>0.0 0.0 0.0</gml:pos>
                                            <gml:pos>0.0 1.0 0.0</gml:pos>
                                            <gml:pos>1.0 1.0 0.0</gml:pos>
                                            <gml:pos>1.0 0.0 0.0</gml:pos>
                                            <gml:pos>0.0 0.0 0.0</gml:pos>
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
def sample_citygml_file(tmp_path, sample_citygml_content):
    """Erstellt eine temporäre CityGML-Datei für Tests."""
    citygml_file = tmp_path / "test.gml"
    citygml_file.write_text(sample_citygml_content)
    return citygml_file

@pytest.fixture
def sample_citygml_tree(sample_citygml_content):
    """Erstellt einen XML-Baum aus dem Beispiel-CityGML-Inhalt für Tests."""
    return ET.ElementTree(ET.fromstring(sample_citygml_content))

@pytest.fixture
def citygml_namespaces():
    """Liefert die CityGML-Namespaces für Tests."""
    return {
        'core': 'http://www.opengis.net/citygml/2.0',
        'bldg': 'http://www.opengis.net/citygml/building/2.0',
        'gml': 'http://www.opengis.net/gml'
    } 
"""Tests für den CityGML-Analyzer."""

import pytest
from pathlib import Path
from lxml import etree
from pipeline.data_sources.citygml_analyzer import CityGMLAnalyzer, analyze_citygml_structure

@pytest.fixture
def sample_citygml():
    """Beispiel-CityGML für Tests."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <core:CityModel xmlns:core="http://www.opengis.net/citygml/1.0"
                    xmlns:bldg="http://www.opengis.net/citygml/building/1.0"
                    xmlns:gml="http://www.opengis.net/gml">
        <core:cityObjectMember>
            <bldg:Building gml:id="BLDG_0001">
                <bldg:measuredHeight>10.0</bldg:measuredHeight>
                <bldg:function>residential</bldg:function>
                <bldg:lod2Solid>
                    <gml:Solid>
                        <gml:exterior>
                            <gml:CompositeSurface>
                                <gml:surfaceMember>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>
                                                    0 0 0  0 1 0  1 1 0  1 0 0  0 0 0
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
        </core:cityObjectMember>
        <core:cityObjectMember>
            <bldg:Building gml:id="BLDG_0002">
                <bldg:measuredHeight>15.0</bldg:measuredHeight>
                <bldg:function>commercial</bldg:function>
                <bldg:lod1Solid>
                    <gml:Solid>
                        <gml:exterior>
                            <gml:CompositeSurface>
                                <gml:surfaceMember>
                                    <gml:Polygon>
                                        <gml:exterior>
                                            <gml:LinearRing>
                                                <gml:posList>
                                                    2 2 0  2 3 0  3 3 0  3 2 0  2 2 0
                                                </gml:posList>
                                            </gml:LinearRing>
                                        </gml:exterior>
                                    </gml:Polygon>
                                </gml:surfaceMember>
                            </gml:CompositeSurface>
                        </gml:exterior>
                    </gml:Solid>
                </bldg:lod1Solid>
            </bldg:Building>
        </core:cityObjectMember>
    </core:CityModel>
    """

@pytest.fixture
def test_file(tmp_path, sample_citygml):
    """Erstellt eine temporäre CityGML-Testdatei."""
    test_file = tmp_path / "test.gml"
    test_file.write_text(sample_citygml)
    return test_file

def test_analyzer_initialization():
    """Test der Analyzer-Initialisierung."""
    analyzer = CityGMLAnalyzer()
    assert analyzer.stats['building_count'] == 0
    assert isinstance(analyzer.stats['tag_counts'], defaultdict)
    assert isinstance(analyzer.stats['attribute_keys'], set)
    assert isinstance(analyzer.stats['lod_levels'], defaultdict)

def test_analyze_pos_list(test_file):
    """Test der posList-Analyse."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert result['pos_list_stats']['count'] == 2
    assert result['pos_list_stats']['min_coords'] == 5
    assert result['pos_list_stats']['max_coords'] == 5
    assert result['pos_list_stats']['total_coords'] == 10

def test_analyze_building_count(test_file):
    """Test der Gebäudezählung."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert result['building_count'] == 2

def test_analyze_lod_levels(test_file):
    """Test der LoD-Level-Erkennung."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert result['lod_levels']['LoD2'] == 1
    assert result['lod_levels']['LoD1'] == 1

def test_analyze_namespaces(test_file):
    """Test der Namespace-Erkennung."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert 'core' in result['namespaces']
    assert 'bldg' in result['namespaces']
    assert 'gml' in result['namespaces']

def test_analyze_tags(test_file):
    """Test der Tag-Zählung."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert result['tag_counts']['bldg:Building'] == 2
    assert result['tag_counts']['bldg:measuredHeight'] == 2
    assert result['tag_counts']['bldg:function'] == 2

def test_analyze_attributes(test_file):
    """Test der Attribut-Erkennung."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='dict')
    
    assert '{http://www.opengis.net/gml}id' in result['attribute_keys']

def test_yaml_output(test_file):
    """Test der YAML-Ausgabe."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file(test_file, output_format='yaml')
    
    assert isinstance(result, str)
    assert 'namespaces:' in result
    assert 'building_count: 2' in result

def test_invalid_file():
    """Test mit ungültiger Datei."""
    analyzer = CityGMLAnalyzer()
    result = analyzer.analyze_file('nonexistent.gml')
    assert result is None

def test_convenience_function(test_file):
    """Test der Convenience-Funktion."""
    result = analyze_citygml_structure(test_file, output_format='dict')
    
    assert result['building_count'] == 2
    assert len(result['namespaces']) == 3
    assert result['pos_list_stats']['count'] == 2 
"""
Integrationstests für den CEA-Geometrie-Prozessor mit echten CityGML-Daten.
"""
import pytest
import geopandas as gpd
from lxml import etree
import pandas as pd
from shapely.geometry import Polygon, box
from pipeline.processing.cea.geometry.processor import CEAGeometryProcessor
from pipeline.processing.citygml_processor import CityGMLProcessor
from pipeline.data_sources.citygml.client import CityGMLBaseClient
from pathlib import Path
import os

@pytest.fixture
def config():
    return {
        'default_building_height': 12.0,
        'crs': 'EPSG:31256',  # MGI / Austria GK East
        'simplify_tolerance': 0.1,
        'citygml': {
            'namespaces': {
                'gml': 'http://www.opengis.net/gml',
                'bldg': 'http://www.opengis.net/citygml/building/1.0',
                'gen': 'http://www.opengis.net/citygml/generics/1.0',
                'core': 'http://www.opengis.net/citygml/1.0'
            }
        }
    }

@pytest.fixture
def citygml_processor(config):
    return CityGMLProcessor(config)

@pytest.fixture
def geometry_processor(config):
    return CEAGeometryProcessor(config)

@pytest.fixture
def citygml_data(config):
    """Lädt die Test-CityGML-Datei."""
    # Korrigierter Pfad zur CityGML-Datei
    file_path = Path('data/raw/citygml/099082.gml')
    if not file_path.exists():
        pytest.skip(f"CityGML-Datei nicht gefunden: {file_path}")
    
    client = CityGMLBaseClient(config['citygml']['namespaces'])
    
    # Lade CityGML-Datei
    root = client.load_citygml(str(file_path))
    if root is None:
        return gpd.GeoDataFrame()
        
    # Finde Gebäude
    buildings = client.find_buildings(root)
    if not buildings:
        return gpd.GeoDataFrame()
        
    # Konvertiere zu GeoDataFrame
    geometries = []
    attributes = []
    
    for building in buildings:
        # Extrahiere Grundrisspolygon aus GroundSurface
        ground_surfaces = building.findall('.//bldg:GroundSurface//gml:posList', client.namespaces)
        if ground_surfaces:
            # Verwende die erste Grundfläche
            footprint = ground_surfaces[0].text
            if footprint:
                # Debug-Ausgabe
                print(f"\nGebäude-ID: {building.get('{http://www.opengis.net/gml}id', '')}")
                print(f"Rohe Koordinaten: {footprint}")
                
                # Konvertiere zu Polygon
                coords = [float(x) for x in footprint.split()]
                print(f"Koordinaten als Liste: {coords}")
                
                # Prüfe, ob die Anzahl der Koordinaten durch 3 teilbar ist (x,y,z)
                if len(coords) % 3 != 0:
                    print(f"⚠️ Ungültige Anzahl von Koordinaten: {len(coords)}")
                    continue
                    
                # Erstelle Punktpaare (x,y), ignoriere z-Koordinate
                points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
                print(f"Punktpaare: {points}")
                
                if len(points) >= 3:
                    # Prüfe, ob das Polygon geschlossen ist
                    if points[0] != points[-1]:
                        points.append(points[0])  # Schließe das Polygon
                        
                    try:
                        poly = Polygon(points)
                        if not poly.is_valid:
                            print(f"⚠️ Ungültiges Polygon")
                            continue
                            
                        geometries.append(poly)
                        # Extrahiere Höhe aus generischen Attributen
                        height = 12.0  # Standardhöhe
                        height_attr = building.find('.//gen:stringAttribute[gen:name="HoeheDach"]/gen:value', client.namespaces)
                        if height_attr is not None and height_attr.text:
                            try:
                                height = float(height_attr.text)
                            except ValueError:
                                pass
                                
                        attributes.append({
                            'building_id': building.get('{http://www.opengis.net/gml}id', ''),
                            'height': height
                        })
                    except Exception as e:
                        print(f"⚠️ Fehler beim Erstellen des Polygons: {str(e)}")
                else:
                    print(f"⚠️ Zu wenige Punkte für ein Polygon: {len(points)}")
    
    if not geometries:
        return gpd.GeoDataFrame()
        
    df = pd.DataFrame(attributes)
    gdf = gpd.GeoDataFrame(df, geometry=geometries, crs='EPSG:31256')
    return gdf

def test_process_real_building_geometry(citygml_processor, geometry_processor, citygml_data):
    """Testet die Verarbeitung eines echten Gebäudes aus den CityGML-Daten."""
    assert not citygml_data.empty, "Keine Gebäude in den CityGML-Daten gefunden"
    
    # Verarbeite das erste Gebäude
    building_data = citygml_data.iloc[0]
    
    # Verarbeite mit CEA-Geometrie-Prozessor
    result = geometry_processor.process({
        'geometry': building_data.geometry,
        'height': building_data.height
    })
    
    # Validiere Ergebnisse
    assert result is not None
    assert isinstance(result, dict)
    assert 'area' in result
    assert result['area'] > 0
    assert 'height' in result
    assert result['height'] > 0
    assert 'orientation' in result
    assert 0 <= result['orientation'] <= 180
    assert 'footprint' in result
    assert isinstance(result['footprint'], dict)
    
    # Prüfe Footprint-Details
    footprint = result['footprint']
    assert footprint['width'] > 0
    assert footprint['length'] > 0
    assert footprint['min_x'] < footprint['max_x']
    assert footprint['min_y'] < footprint['max_y']
    
    print(f"\nVerarbeitete Gebäudegeometrie:")
    print(f"Fläche: {result['area']:.2f} m²")
    print(f"Höhe: {result['height']:.2f} m")
    print(f"Orientierung: {result['orientation']:.2f}°")
    print(f"Abmessungen: {footprint['width']:.2f} x {footprint['length']:.2f} m")

def test_process_all_buildings(citygml_processor, geometry_processor, citygml_data):
    """Testet die Verarbeitung aller Gebäude aus den CityGML-Daten."""
    assert not citygml_data.empty, "Keine Gebäude in den CityGML-Daten gefunden"
    
    results = []
    for _, building_data in citygml_data.iterrows():
        result = geometry_processor.process({
            'geometry': building_data.geometry,
            'height': building_data.height
        })
        if result:
            results.append(result)
    
    assert len(results) > 0, "Keine Gebäude erfolgreich verarbeitet"
    
    # Statistiken berechnen
    total_area = sum(r['area'] for r in results)
    avg_height = sum(r['height'] for r in results) / len(results)
    
    print(f"\nGesamtstatistik:")
    print(f"Verarbeitete Gebäude: {len(results)}")
    print(f"Gesamtfläche: {total_area:.2f} m²")
    print(f"Durchschnittshöhe: {avg_height:.2f} m")

def test_export_buildings_geojson(citygml_processor, geometry_processor, citygml_data):
    """Exportiert die verarbeiteten Gebäude als GeoJSON für QGIS."""
    assert not citygml_data.empty, "Keine Gebäude in den CityGML-Daten gefunden"
    
    # Erstelle Ausgabeordner
    output_dir = Path('outputs/results')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Verarbeite alle Gebäude
    processed_buildings = []
    for _, building_data in citygml_data.iterrows():
        result = geometry_processor.process({
            'geometry': building_data.geometry,
            'height': building_data.height
        })
        if result:
            processed_buildings.append({
                'geometry': result['geometry'],
                'height': result['height'],
                'area': result['area'],
                'orientation': result['orientation'],
                'building_id': building_data.get('building_id', '')
            })
    
    # Erstelle GeoDataFrame
    gdf = gpd.GeoDataFrame(processed_buildings, crs='EPSG:31256')
    
    # Exportiere als GeoJSON
    output_file = output_dir / 'processed_buildings.geojson'
    gdf.to_file(output_file, driver='GeoJSON')
    
    print(f"\nGebäude wurden exportiert nach: {output_file}")
    print(f"Sie können diese Datei jetzt in QGIS öffnen.") 
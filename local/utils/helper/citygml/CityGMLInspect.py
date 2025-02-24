import xml.etree.ElementTree as ET
from pathlib import Path
import yaml
from typing import List, Dict
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon
import pandas as pd
import numpy as np
import math
from scipy.spatial import ConvexHull

class CityGMLInspector:
    def __init__(self, citygml_path: Path):
        self.citygml_path = Path(citygml_path)
        self.ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml'
        }
        
        # Lade das XML-Dokument
        try:
            tree = ET.parse(str(self.citygml_path))
            self.root = tree.getroot()
            print(f"CityGML-Datei erfolgreich geladen: {self.citygml_path.name}")
        except Exception as e:
            print(f"Fehler beim Laden der CityGML-Datei: {str(e)}")
            raise
        
        # Lade Mapping-Datei aus dem neuen Pfad
        mapping_path = Path(__file__).parent / "mapping" / "citygml_to_ifc.yml"
        with open(mapping_path, 'r', encoding='utf-8') as f:
            self.mapping = yaml.safe_load(f)
        
        # Namespaces aus Mapping-Datei laden
        self.ns = self.mapping['namespaces']['citygml_1_0']
        
    def inspect_file(self):
        """Analysiert die CityGML-Datei und gibt strukturierte Gebäudedaten zurück"""
        try:
            print(f"Analysiere CityGML-Datei: {self.citygml_path.name}")
            
            # Sammle alle relevanten Gebäudedaten
            buildings_data = []
            
            for building in self.root.findall('.//bldg:Building', self.ns):
                building_id = self._extract_id(building)
                height, height_source = self._extract_height(building)
                roof_type = self._extract_roof_type(building)
                
                # Extrahiere Geometrien
                footprint = self._extract_footprint(building)
                wall_geometries = []
                roof_geometries = []
                
                # Sammle Wandgeometrien
                for wall in building.findall('.//bldg:WallSurface', self.ns):
                    points = self._extract_surface_points(wall)
                    if points:
                        wall_geometries.append(points)
                
                # Sammle Dachgeometrien
                for roof in building.findall('.//bldg:RoofSurface', self.ns):
                    points = self._extract_surface_points(roof)
                    if points:
                        roof_geometries.append(points)
                
                # Geschossanalyse
                stories = self._analyze_stories(
                    [p[2] for geom in wall_geometries for p in geom]
                ) if wall_geometries else []
                
                # Strukturiere Gebäudedaten
                building_data = {
                    'id': building_id,
                    'height': height,
                    'height_source': height_source,
                    'roof_type': roof_type,
                    'footprint': footprint,
                    'wall_geometries': wall_geometries,
                    'roof_geometries': roof_geometries,
                    'stories': stories,
                    'area': footprint.area if footprint else 0.0
                }
                
                buildings_data.append(building_data)
                
                # Debug-Ausgabe
                print(f"\nGebäude {building_id}:")
                print(f"- Höhe: {height:.2f}m ({height_source})")
                print(f"- Dachtyp: {roof_type}")
                print(f"- Anzahl Wände: {len(wall_geometries)}")
                print(f"- Anzahl Dachflächen: {len(roof_geometries)}")
                print(f"- Anzahl Geschosse: {len(stories)}")
            
            return buildings_data
            
        except Exception as e:
            print(f"Fehler bei der Dateianalyse: {str(e)}")
            return None

    def _analyze_buildings(self, city_objects):
        """Analysiert alle Gebäude in den cityObjectMember-Elementen"""
        buildings_found = 0
        building_types = {}
        roof_types = {}
        heights = []
        
        for city_object in city_objects:
            # Verbesserte Suche nach Gebäuden
            building = city_object.find('.//bldg:Building', self.ns)
            if building is None:
                building = city_object.find('.//bldg:BuildingPart', self.ns)
            
            if building is not None:
                buildings_found += 1
                
                # Sammle Statistiken
                building_type = building.tag.split('}')[-1]
                building_types[building_type] = building_types.get(building_type, 0) + 1
                
                roof_type = building.find('.//bldg:roofType', self.ns)
                if roof_type is not None and roof_type.text:
                    roof_types[roof_type.text] = roof_types.get(roof_type.text, 0) + 1
                
                height = building.find('.//bldg:measuredHeight', self.ns)
                if height is not None and height.text:
                    heights.append(float(height.text))
        
        # Ausgabe der Statistiken
        print(f"\n=== Gesamtstatistiken ===")
        print(f"Gesamtanzahl Gebäude: {buildings_found}")
        print("\nGebäudetypen:")
        for btype, count in building_types.items():
            print(f"- {btype}: {count}")
        
        print("\nDachtypen:")
        for rtype, count in roof_types.items():
            print(f"- {rtype}: {count}")
        
        if heights:
            print("\nHöhenstatistik:")
            print(f"- Minimale Höhe: {min(heights):.2f}m")
            print(f"- Maximale Höhe: {max(heights):.2f}m")
            print(f"- Durchschnittliche Höhe: {sum(heights)/len(heights):.2f}m")
    
    def _analyze_single_building(self, building):
        """Analysiert ein einzelnes Gebäude und seine Teilgebäude im Detail"""
        print(f"\n=== Detailanalyse Gebäude ===")
        building_id = self._extract_id(building)
        print(f"Gebäude-ID: {building_id}")
        
        # Analysiere Hauptgebäude
        main_structure = self._analyze_building_part(building, "Hauptgebäude")
        
        # Analysiere Teilgebäude
        building_parts = building.findall('.//bldg:BuildingPart', self.ns)
        if building_parts:
            print(f"\n=== Teilgebäude ({len(building_parts)}) ===")
            part_structures = []
            for idx, part in enumerate(building_parts, 1):
                part_id = part.get('{http://www.opengis.net/gml}id', 'Keine ID')
                print(f"\nTeilgebäude {idx} (ID: {part_id})")
                part_structure = self._analyze_building_part(part, f"Teilgebäude {idx}")
                part_structures.append((part_id, part_structure))
            
            # Analysiere Beziehungen zwischen Teilgebäuden
            self._analyze_building_relationships(part_structures)

    def _analyze_building_part(self, building_part, part_name):
        """Analysiert einen Gebäudeteil im Detail und gibt Strukturinformationen zurück"""
        structure_info = {
            'ground_levels': set(),
            'roof_levels': set(),
            'wall_connections': [],
            'openings': [],
            'stories': [],
            'volumes': [],
            'total_volume': 0.0
        }
        
        # Sammle alle Höheninformationen
        all_z_coords = []
        
        # Grundflächen analysieren
        ground_surfaces = building_part.findall('.//bldg:GroundSurface', self.ns)
        ground_geometries = []
        if ground_surfaces:
            print(f"\n{part_name} - Grundflächen ({len(ground_surfaces)}):")
            for idx, surface in enumerate(ground_surfaces, 1):
                surface_id = surface.get('{http://www.opengis.net/gml}id', 'Keine ID')
                points = self._extract_surface_points(surface)
                if points:
                    ground_geometries.append(points)
                    z_coords = [p[2] for p in points]
                    all_z_coords.extend(z_coords)
                    structure_info['ground_levels'].add(round(z_coords[0], 2))
                    area = self._calculate_polygon_area(points)
                    
                    print(f"- Fläche {idx} (ID: {surface_id}):")
                    print(f"  Anzahl Punkte: {len(points)}")
                    print(f"  Höhe: {z_coords[0]:.2f}m")
                    print(f"  Grundfläche: {area:.2f}m²")
        
        # Wandflächen und Öffnungen analysieren
        wall_surfaces = building_part.findall('.//bldg:WallSurface', self.ns)
        wall_geometries = []
        if wall_surfaces:
            print(f"\n{part_name} - Wandflächen ({len(wall_surfaces)}):")
            for idx, surface in enumerate(wall_surfaces, 1):
                surface_id = surface.get('{http://www.opengis.net/gml}id', 'Keine ID')
                points = self._extract_surface_points(surface)
                if points:
                    wall_geometries.append(points)
                    z_coords = [p[2] for p in points]
                    all_z_coords.extend(z_coords)
                    
                    # Analysiere Öffnungen
                    openings = self._analyze_openings(surface)
                    if openings:
                        structure_info['openings'].extend(openings)
                        print(f"- Wand {idx} (ID: {surface_id}) mit {len(openings)} Öffnungen:")
                        for opening in openings:
                            print(f"  - {opening['type']}: {opening['width']:.2f}m x {opening['height']:.2f}m")
                            print(f"    Position: {opening['bottom_level']:.2f}m bis {opening['top_level']:.2f}m")
                            print(f"    Fläche: {opening['area']:.2f}m²")
        
        # Dachflächen analysieren
        roof_surfaces = building_part.findall('.//bldg:RoofSurface', self.ns)
        roof_geometries = []
        if roof_surfaces:
            print(f"\n{part_name} - Dachflächen ({len(roof_surfaces)}):")
            for idx, surface in enumerate(roof_surfaces, 1):
                surface_id = surface.get('{http://www.opengis.net/gml}id', 'Keine ID')
                points = self._extract_surface_points(surface)
                if points:
                    roof_geometries.append(points)
                    z_coords = [p[2] for p in points]
                    all_z_coords.extend(z_coords)
                    structure_info['roof_levels'].add(round(min(z_coords), 2))
                    area = self._calculate_polygon_area(points)
                    
                    print(f"- Fläche {idx} (ID: {surface_id}):")
                    print(f"  Dachfläche: {area:.2f}m²")
                    print(f"  Höhenbereich: {min(z_coords):.2f}m bis {max(z_coords):.2f}m")
        
        # Geschoss- und Volumenanalyse
        if all_z_coords:
            stories = self._analyze_stories(all_z_coords)
            volumes = self._calculate_story_volumes(stories, ground_geometries, wall_geometries, roof_geometries)
            
            print(f"\n{part_name} - Geschoss- und Volumenanalyse:")
            total_volume = 0.0
            for idx, (story, volume) in enumerate(zip(stories, volumes), 1):
                total_volume += volume
                print(f"Geschoss {idx}:")
                print(f"- Höhenbereich: {story['bottom_level']:.2f}m bis {story['top_level']:.2f}m")
                print(f"- Geschosshöhe: {story['height']:.2f}m")
                print(f"- Geschossvolumen: {volume:.2f}m³")
                
                # Öffnungen im Geschoss
                story_openings = [o for o in structure_info['openings'] 
                                if story['bottom_level'] <= o['bottom_level'] <= story['top_level']]
                if story_openings:
                    print(f"- Öffnungen im Geschoss:")
                    doors = [o for o in story_openings if o['type'] == 'DOOR']
                    windows = [o for o in story_openings if o['type'] == 'WINDOW']
                    if doors:
                        print(f"  - Türen: {len(doors)}")
                    if windows:
                        print(f"  - Fenster: {len(windows)}")
            
            print(f"\nGesamtvolumen {part_name}: {total_volume:.2f}m³")
            structure_info['total_volume'] = total_volume
        
        # Erweiterte Ausgabe der Öffnungsanalyse
        if structure_info['openings']:
            print(f"\n{part_name} - Öffnungsanalyse:")
            doors = [o for o in structure_info['openings'] if o['type'] == 'DOOR']
            windows = [o for o in structure_info['openings'] if o['type'] == 'WINDOW']
            
            if doors:
                print(f"\nTüren ({len(doors)}):")
                for idx, door in enumerate(doors, 1):
                    print(f"- Tür {idx}:")
                    print(f"  Funktion: {door['function']}")
                    print(f"  Maße: {door['width']:.2f}m x {door['height']:.2f}m")
                    print(f"  Fläche: {door['area']:.2f}m²")
                    print(f"  Position: {door['bottom_level']:.2f}m bis {door['top_level']:.2f}m")
                    print(f"  Orientierung: {door['orientation']}")
            
            if windows:
                print(f"\nFenster ({len(windows)}):")
                for idx, window in enumerate(windows, 1):
                    print(f"- Fenster {idx}:")
                    print(f"  Funktion: {window['function']}")
                    print(f"  Maße: {window['width']:.2f}m x {window['height']:.2f}m")
                    print(f"  Fläche: {window['area']:.2f}m²")
                    print(f"  Position: {window['bottom_level']:.2f}m bis {window['top_level']:.2f}m")
                    print(f"  Orientierung: {window['orientation']}")
        
        # Zusätzliche Validierung der Volumina
        if volumes:
            print(f"\nVolumenanalyse {part_name}:")
            print(f"Gesamtvolumen: {sum(volumes):.2f}m³")
            print("Volumen pro Geschoss:")
            for idx, volume in enumerate(volumes, 1):
                print(f"- Geschoss {idx}: {volume:.2f}m³")
            
            # Prüfe auf ungewöhnliche Abweichungen
            avg_volume = sum(volumes) / len(volumes)
            deviations = [abs(v - avg_volume) / avg_volume * 100 for v in volumes if v > 0]
            if deviations and max(deviations) > 20:  # Mehr als 20% Abweichung
                print("\nHinweis: Ungewöhnliche Volumenverteilung!")
                print(f"Durchschnittsvolumen: {avg_volume:.2f}m³")
                print(f"Maximale Abweichung: {max(deviations):.1f}%")
        
        return structure_info

    def _analyze_building_relationships(self, part_structures):
        """Analysiert die Beziehungen zwischen Gebäudeteilen"""
        print("\n=== Gebäudeteil-Beziehungen ===")
        
        for i, (id1, struct1) in enumerate(part_structures):
            for j, (id2, struct2) in enumerate(part_structures[i+1:], i+1):
                # Berechne Überlappungsbereich
                overlap = self._calculate_overlap(struct1, struct2)
                if overlap:
                    print(f"\nBeziehung zwischen {id1} und {id2}:")
                    print(f"- Überlappungstyp: {overlap['type']}")
                    print(f"- Überlappungshöhe: {overlap['height']:.2f}m")
                    if overlap['shared_levels']:
                        print("- Gemeinsame Geschosse:")
                        for level in overlap['shared_levels']:
                            print(f"  * Höhe: {level:.2f}m")
                    if overlap['volume'] > 0:
                        print(f"- Überlappungsvolumen: {overlap['volume']:.2f}m³")

    def _calculate_overlap(self, struct1, struct2):
        """Berechnet detaillierte Überlappungsinformationen zwischen zwei Gebäudeteilen"""
        # Höhenbereiche
        min_height1 = min(struct1['ground_levels'])
        max_height1 = max(struct1['roof_levels'])
        min_height2 = min(struct2['ground_levels'])
        max_height2 = max(struct2['roof_levels'])
        
        # Prüfe auf Überlappung
        if max_height1 < min_height2 or min_height1 > max_height2:
            return None
        
        # Berechne Überlappungsbereich
        overlap_bottom = max(min_height1, min_height2)
        overlap_top = min(max_height1, max_height2)
        overlap_height = overlap_top - overlap_bottom
        
        # Finde gemeinsame Geschosshöhen
        shared_levels = set()
        for level in struct1['ground_levels'].union(struct1['roof_levels']):
            if min_height2 <= level <= max_height2:
                shared_levels.add(level)
        for level in struct2['ground_levels'].union(struct2['roof_levels']):
            if min_height1 <= level <= max_height1:
                shared_levels.add(level)
        
        # Bestimme Überlappungstyp
        if min_height1 == min_height2 and max_height1 == max_height2:
            overlap_type = "Vollständige Überlappung"
        elif min_height1 <= min_height2 and max_height1 >= max_height2:
            overlap_type = "Gebäude 2 in Gebäude 1 enthalten"
        elif min_height2 <= min_height1 and max_height2 >= max_height1:
            overlap_type = "Gebäude 1 in Gebäude 2 enthalten"
        else:
            overlap_type = "Teilweise Überlappung"
        
        # Schätze Überlappungsvolumen
        overlap_volume = 0.0
        if len(shared_levels) >= 2:
            # Berechne durchschnittliche Grundfläche für Überlappungsbereich
            areas1 = [self._calculate_polygon_area(points) for points in struct1.get('ground_geometries', [])]
            areas2 = [self._calculate_polygon_area(points) for points in struct2.get('ground_geometries', [])]
            if areas1 and areas2:
                avg_area = min(min(areas1), min(areas2))  # Konservative Schätzung
                overlap_volume = avg_area * overlap_height
        
        return {
            'type': overlap_type,
            'height': overlap_height,
            'shared_levels': sorted(shared_levels),
            'volume': overlap_volume,
            'bottom': overlap_bottom,
            'top': overlap_top
        }

    def _calculate_roof_slope(self, points):
        """Berechnet die Dachneigung in Grad"""
        if len(points) < 3:
            return 0.0
        
        # Vereinfachte Berechnung über Höhendifferenz
        z_coords = [p[2] for p in points]
        height_diff = max(z_coords) - min(z_coords)
        
        # Berechne horizontale Distanz
        p1, p2 = points[0], points[-1]
        horizontal_dist = ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
        
        if horizontal_dist > 0:
            return math.degrees(math.atan(height_diff/horizontal_dist))
        return 0.0

    def _analyze_wall_geometry(self, points):
        """Analysiert die Wandgeometrie"""
        z_coords = [p[2] for p in points]
        height = max(z_coords) - min(z_coords)
        
        # Berechne Wandrichtung
        p1, p2 = points[0], points[1]
        direction = math.degrees(math.atan2(p2[1]-p1[1], p2[0]-p1[0]))
        
        return {
            'height': height,
            'direction': direction,
            'bottom_level': min(z_coords),
            'top_level': max(z_coords),
            'points': points
        }

    def _analyze_opening(self, opening):
        """Analysiert eine Öffnung (Tür/Fenster)"""
        opening_type = opening.get('type', 'UNKNOWN')
        points = self._extract_surface_points(opening)
        
        if points:
            z_coords = [p[2] for p in points]
            width = self._calculate_width(points)
            height = max(z_coords) - min(z_coords)
            
            return {
                'type': opening_type,
                'width': width,
                'height': height,
                'bottom_level': min(z_coords),
                'top_level': max(z_coords)
            }
        return None

    def _analyze_stories(self, z_coords, min_story_height=2.5, max_story_height=4.0):
        """Analysiert Geschosse basierend auf Z-Koordinaten"""
        unique_levels = sorted(set(round(z, 2) for z in z_coords))
        stories = []
        current_bottom = unique_levels[0]
        
        for z in unique_levels[1:]:
            height = z - current_bottom
            # Wenn die Höhe größer als max_story_height ist, teile in mehrere Geschosse
            if height > max_story_height:
                num_stories = math.ceil(height / max_story_height)
                story_height = height / num_stories
                
                for i in range(num_stories):
                    story_bottom = current_bottom + (i * story_height)
                    story_top = story_bottom + story_height
                    stories.append({
                        'bottom_level': story_bottom,
                        'top_level': story_top,
                        'height': story_height,
                        'openings': [],
                        'volume': 0.0  # Wird später berechnet
                    })
            elif height >= min_story_height:
                stories.append({
                    'bottom_level': current_bottom,
                    'top_level': z,
                    'height': height,
                    'openings': [],
                    'volume': 0.0  # Wird später berechnet
                })
            current_bottom = z
        
        return stories

    def _print_story_analysis(self, stories, part_name):
        """Gibt die Geschossanalyse aus"""
        print(f"\n{part_name} - Geschossanalyse:")
        for idx, story in enumerate(stories, 1):
            print(f"Geschoss {idx}:")
            print(f"- Höhenbereich: {story['bottom_level']:.2f}m bis {story['top_level']:.2f}m")
            print(f"- Geschosshöhe: {story['height']:.2f}m")

    def _find_adjacent_surfaces(self, surface_points, all_surfaces, tolerance=0.01):
        """Findet angrenzende Flächen basierend auf gemeinsamen Kanten"""
        adjacent = []
        surface_edges = set(tuple(sorted([tuple(p1), tuple(p2)]))
                       for p1, p2 in zip(surface_points, surface_points[1:] + [surface_points[0]]))
        
        for other_surface in all_surfaces:
            other_points = self._extract_surface_points(other_surface)
            other_edges = set(tuple(sorted([tuple(p1), tuple(p2)]))
                         for p1, p2 in zip(other_points, other_points[1:] + [other_points[0]]))
            
            # Prüfe auf gemeinsame Kanten
            if surface_edges & other_edges:
                adjacent.append(other_surface)
        
        return adjacent

    def _validate_building(self, building: ET.Element, building_data: dict) -> dict:
        """Führt Plausibilitätsprüfungen für ein Gebäude durch"""
        validation_results = {
            'is_valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Lade Validierungsregeln aus dem Mapping
        validations = self.mapping.get('validations', {}).get('building', {})
        min_height = validations.get('min_height', 2.0)
        max_height = validations.get('max_height', 100.0)
        min_area = validations.get('min_footprint_area', 4.0)
        
        # Prüfe Höhe
        height = building_data.get('height')
        if height is not None:
            if height < min_height:
                validation_results['warnings'].append(
                    f"Gebäudehöhe ({height:.2f}m) unter Minimum von {min_height}m"
                )
            elif height > max_height:
                validation_results['warnings'].append(
                    f"Gebäudehöhe ({height:.2f}m) über Maximum von {max_height}m"
                )
        
        # Prüfe Grundfläche
        if 'geometry' in building_data:
            area = building_data['geometry'].area
            if area < min_area:
                validation_results['warnings'].append(
                    f"Grundfläche ({area:.2f}m²) unter Minimum von {min_area}m²"
                )
        
        # Prüfe Dachtyp und erforderliche Flächen
        roof_type = building_data.get('roof_type')
        if roof_type:
            required_surfaces = self.mapping['surfaces']['roof_surface']['attributes']['roof_type']['validation']['required_surfaces']
            min_surfaces = required_surfaces.get(roof_type, required_surfaces['default'])
            
            roof_surfaces = building.findall('.//bldg:RoofSurface', self.ns)
            if len(roof_surfaces) < min_surfaces:
                validation_results['warnings'].append(
                    f"Zu wenige Dachflächen für Typ {roof_type} (gefunden: {len(roof_surfaces)}, erwartet: {min_surfaces})"
                )
        
        return validation_results

    def get_building_data(self) -> gpd.GeoDataFrame:
        """Extrahiert alle relevanten Gebäudedaten mit Validierung"""
        buildings = self.root.findall('.//bldg:Building', self.ns)
        
        data = []
        validation_issues = []
        
        for building in buildings:
            building_id = self._extract_id(building)
            footprint = self._extract_footprint(building)
            
            if footprint:
                height, source = self._extract_height(building)
                roof_type = self._extract_roof_type(building)
                
                building_data = {
                    'building_id': building_id,
                    'geometry': footprint,
                    'height': height,
                    'height_source': source,
                    'roof_type': roof_type
                }
                
                # Validierung durchführen
                validation = self._validate_building(building, building_data)
                if validation['warnings'] or validation['errors']:
                    validation_issues.append({
                        'building_id': building_id,
                        'warnings': validation['warnings'],
                        'errors': validation['errors']
                    })
                
                data.append(building_data)
        
        # Ausgabe der Validierungsergebnisse
        if validation_issues:
            print("\n=== Validierungsprobleme ===")
            for issue in validation_issues:
                print(f"\nGebäude {issue['building_id']}:")
                if issue['warnings']:
                    print("Warnungen:")
                    for warning in issue['warnings']:
                        print(f"- {warning}")
                if issue['errors']:
                    print("Fehler:")
                    for error in issue['errors']:
                        print(f"- {error}")
        
        return gpd.GeoDataFrame(data)

    def _extract_footprint(self, building):
        """Extrahiert den Grundriss eines Gebäudes"""
        try:
            # Suche nach der Grundfläche
            ground_surface = building.find('.//bldg:GroundSurface', self.ns)
            if ground_surface is None:
                print("Keine Grundfläche gefunden")
                return None

            # Extrahiere die Koordinaten
            pos_list = ground_surface.find('.//gml:posList', self.ns)
            if pos_list is None:
                print("Keine Koordinatenliste gefunden")
                return None

            # Konvertiere den String in eine Liste von Koordinaten
            coords = [float(x) for x in pos_list.text.split()]
            
            # Debug-Ausgabe
            print(f"Gefundene Koordinaten: {len(coords)} Werte")
            
            # Prüfe ob die Anzahl der Koordinaten durch 3 teilbar ist (x,y,z Tripel)
            if len(coords) % 3 != 0:
                print(f"Warnung: Ungerade Anzahl von Koordinaten: {len(coords)}")
                return None

            # Erstelle Punktepaare (x,y) aus den Koordinaten, überspringe z-Werte
            points = [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            
            # Debug-Ausgabe
            print(f"Erstellte Punkte: {len(points)}")

            # Erstelle ein Polygon aus den Punkten
            from shapely.geometry import Polygon
            return Polygon(points)

        except Exception as e:
            print(f"Fehler beim Extrahieren des Grundrisses: {str(e)}")
            return None

    def _extract_height(self, building: ET.Element) -> tuple[float, str]:
        """Extrahiert die Höhe eines Gebäudes aus verschiedenen möglichen Quellen"""
        try:
            # 1. Versuch: Direkte measuredHeight
            measured_height = building.find('.//bldg:measuredHeight', self.ns)
            if measured_height is not None and measured_height.text:
                return float(measured_height.text), "measuredHeight"

            # 2. Versuch: Berechnung aus LoD2 Solid
            lod2_solid = building.find('.//bldg:lod2Solid', self.ns)
            if lod2_solid is not None:
                z_coords = []
                pos_list = lod2_solid.findall('.//gml:posList', self.ns)
                for pos in pos_list:
                    if pos.text:
                        coords = [float(x) for x in pos.text.split()]
                        z_coords.extend(coords[2::3])
                
                if z_coords:
                    height = max(z_coords) - min(z_coords)
                    return height, "LoD2Solid"

            # 3. Versuch: Berechnung aus LoD2 MultiSurface
            lod2_ms = building.find('.//bldg:lod2MultiSurface', self.ns)
            if lod2_ms is not None:
                z_coords = []
                pos_lists = lod2_ms.findall('.//gml:posList', self.ns)
                for pos in pos_lists:
                    if pos.text:
                        coords = [float(x) for x in pos.text.split()]
                        z_coords.extend(coords[2::3])
                
                if z_coords:
                    height = max(z_coords) - min(z_coords)
                    return height, "LoD2MultiSurface"

            # 4. Versuch: Berechnung aus Stockwerken
            storeys = building.find('.//bldg:storeysAboveGround', self.ns)
            storey_height = building.find('.//bldg:storeyHeightsAboveGround', self.ns)
            if storeys is not None and storeys.text:
                if storey_height is not None and storey_height.text:
                    height = float(storeys.text) * float(storey_height.text)
                    return height, "StoreyHeight"
                height = float(storeys.text) * 3.0
                return height, "StoreyCount"

            return 3.0, "Default"  # Standardhöhe wenn keine andere Information verfügbar

        except (ValueError, TypeError, AttributeError) as e:
            print(f"Fehler bei der Höhenberechnung: {str(e)}")
            return 3.0, "Error"

    def analyze_spatial_distribution(self, gdf: gpd.GeoDataFrame) -> dict:
        """Analysiert die räumliche Verteilung der Gebäude"""
        analysis = {
            'total_buildings': len(gdf),
            'total_area': gdf.area.sum(),
            'total_volume': gdf.volume.sum(),
            'height_stats': gdf.height.describe().to_dict(),
            'area_stats': gdf.area.describe().to_dict(),
            'roof_type_distribution': gdf.roof_type.value_counts().to_dict(),
            'spatial_density': len(gdf) / gdf.total_bounds.area,
            'nearest_neighbor_stats': self._calculate_nearest_neighbor(gdf)
        }
        return analysis

    def _calculate_nearest_neighbor(self, gdf: gpd.GeoDataFrame) -> dict:
        """Berechnet Statistiken zu den nächsten Nachbarn"""
        distances = []
        for idx, building in gdf.iterrows():
            other_buildings = gdf[gdf.index != idx]
            if not other_buildings.empty:
                min_distance = other_buildings.distance(building.geometry).min()
                distances.append(min_distance)
        
        return {
            'mean_distance': np.mean(distances),
            'min_distance': np.min(distances),
            'max_distance': np.max(distances)
        }

    def _extract_id(self, building: ET.Element) -> str:
        """Extrahiert die Gebäude-ID"""
        # Suche nach gml:id Attribut
        gml_id = building.get('{http://www.opengis.net/gml}id')
        if gml_id:
            return gml_id
        
        # Alternativ nach lokalem ID-Attribut suchen
        local_id = building.get('id')
        if local_id:
            return local_id
        
        return "UNKNOWN_ID"

    def _extract_roof_type(self, building: ET.Element) -> str:
        """Extrahiert den Dachtyp"""
        roof_type = building.find('.//bldg:roofType', self.ns)
        if roof_type is not None and roof_type.text:
            return roof_type.text
        return "UNKNOWN_ROOF_TYPE"

    def print_statistics(self):
        """Gibt detaillierte Statistiken aus"""
        buildings = self.root.findall('.//bldg:Building', self.ns)
        
        print("\n=== Gesamtstatistiken ===")
        print(f"Gesamtanzahl Gebäude: {len(buildings)}")
        
        # Dachtypen
        roof_types = {}
        heights = []
        height_sources = {}
        low_buildings = []
        
        for building in buildings:
            # Dachtyp
            roof_type = self._extract_roof_type(building)
            roof_types[roof_type] = roof_types.get(roof_type, 0) + 1
            
            # Höhe
            height, source = self._extract_height(building)
            if height > 0:
                heights.append(height)
                height_sources[source] = height_sources.get(source, 0) + 1
                
                if height < 3.0:
                    low_buildings.append({
                        'id': self._extract_id(building),
                        'height': height,
                        'source': source,
                        'roof_type': roof_type
                    })
        
        print("\nDachtypen:")
        for roof_type, count in roof_types.items():
            print(f"- {roof_type}: {count}")
        
        if heights:
            print("\nHöhenstatistik:")
            print(f"- Minimale Höhe: {min(heights):.2f}m")
            print(f"- Maximale Höhe: {max(heights):.2f}m")
            print(f"- Durchschnittliche Höhe: {sum(heights)/len(heights):.2f}m")
            
            print("\nHöhenverteilung:")
            height_ranges = {
                "0-3m": len([h for h in heights if h < 3]),
                "3-6m": len([h for h in heights if 3 <= h < 6]),
                "6-9m": len([h for h in heights if 6 <= h < 9]),
                "9-12m": len([h for h in heights if 9 <= h < 12]),
                "12-15m": len([h for h in heights if 12 <= h < 15]),
                "15m+": len([h for h in heights if h >= 15])
            }
            for range_name, count in height_ranges.items():
                print(f"- {range_name}: {count} Gebäude")
            
            print("\nHöhenquellen:")
            for source, count in height_sources.items():
                print(f"- {source}: {count} Gebäude")
        
        if low_buildings:
            print("\n=== Analyse niedriger Gebäude (< 3m) ===")
            print(f"Anzahl: {len(low_buildings)}")
            print("\nDetails:")
            for building in low_buildings:
                print(f"- Gebäude {building['id']}:")
                print(f"  Höhe: {building['height']:.2f}m")
                print(f"  Quelle: {building['source']}")
                print(f"  Dachtyp: {building['roof_type']}")
                print()

    def analyze_building_structure(self, building: ET.Element):
        """Analysiert die Gebäudestruktur im Detail"""
        # Geschossanalyse
        storeys = []
        z_levels = set()
        for surface in building.findall('.//bldg:WallSurface', self.ns):
            pos_list = surface.find('.//gml:posList', self.ns)
            if pos_list is not None and pos_list.text:
                coords = [float(x) for x in pos_list.text.split()]
                z_coords = coords[2::3]  # Jede dritte Koordinate ist Z
                z_levels.update([min(z_coords), max(z_coords)])
        
        # Sortierte Z-Levels könnten Geschosse andeuten
        z_levels = sorted(z_levels)
        
        # Flächenbeziehungen
        surface_relations = {}
        for surface in building.findall('.//*[@{http://www.opengis.net/gml}id]', self.ns):
            surface_id = surface.get('{http://www.opengis.net/gml}id')
            surface_type = surface.tag.split('}')[-1]
            
            # Finde angrenzende Flächen durch Koordinatenvergleich
            pos_list = surface.find('.//gml:posList', self.ns)
            if pos_list is not None and pos_list.text:
                coords = [float(x) for x in pos_list.text.split()]
                points = [(coords[i], coords[i+1], coords[i+2]) 
                         for i in range(0, len(coords), 3)]
                surface_relations[surface_id] = {
                    'type': surface_type,
                    'points': points,
                    'adjacent_surfaces': []
                }
        
        # Finde Öffnungen
        openings = building.findall('.//bldg:opening', self.ns)
        
        return {
            'potential_storeys': len(z_levels) - 1,
            'z_levels': z_levels,
            'surface_relations': surface_relations,
            'openings': len(openings)
        }

    def _extract_surface_points(self, surface):
        """Extrahiert die Punkte einer Fläche"""
        pos_list = surface.find('.//gml:posList', self.ns)
        if pos_list is not None and pos_list.text:
            coords = [float(x) for x in pos_list.text.split()]
            # Gruppiere Koordinaten in 3D-Punkte
            points = [(coords[i], coords[i+1], coords[i+2]) 
                     for i in range(0, len(coords), 3)]
            return points
        return None

    def _calculate_width(self, points):
        """Berechnet die Breite zwischen den Punkten"""
        if len(points) < 2:
            return 0.0
        
        # Berechne die horizontale Distanz zwischen den äußersten Punkten
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        width = ((max(x_coords) - min(x_coords))**2 + 
                 (max(y_coords) - min(y_coords))**2)**0.5
        
        return width

    def _calculate_story_volumes(self, stories, ground_geometries, wall_geometries, roof_geometries):
        """Berechnet die Volumina für jedes Geschoss mit verbesserter Methodik"""
        volumes = []
        base_area = None  # Grundfläche des ersten Geschosses
        
        print("\nDebug: Verbesserte Volumenberechnung")
        print(f"Anzahl Geschosse: {len(stories)}")
        print(f"Anzahl Grundflächen: {len(ground_geometries)}")
        print(f"Anzahl Wandflächen: {len(wall_geometries)}")
        
        for idx, story in enumerate(stories, 1):
            story_volume = 0.0
            story_bottom = story['bottom_level']
            story_top = story['top_level']
            story_height = story['height']
            story_points = []  # Initialisiere story_points hier
            
            print(f"\nGeschoss {idx}:")
            print(f"Höhenbereich: {story_bottom:.2f}m - {story_top:.2f}m")
            
            # Methode 1: Direkte Grundfläche
            story_area = 0.0
            for ground_points in ground_geometries:
                ground_z = ground_points[0][2]
                if abs(ground_z - story_bottom) < 0.2:  # 20cm Toleranz
                    area = self._calculate_polygon_area(ground_points)
                    print(f"Gefundene Grundfläche: {area:.2f}m²")
                    story_area = max(story_area, area)
                    if idx == 1:
                        base_area = area  # Speichere Grundfläche des ersten Geschosses
            
            # Methode 2: Wandflächenanalyse
            if story_area == 0.0:
                print("Berechne Grundfläche aus Wandpunkten...")
                for wall_points in wall_geometries:
                    points_in_story = [p for p in wall_points 
                                     if story_bottom - 0.1 <= p[2] <= story_top + 0.1]
                    if points_in_story:
                        # Projiziere auf Geschossebene
                        projected_points = [(p[0], p[1]) for p in points_in_story]
                        story_points.extend(projected_points)
            
            if story_points:
                # Entferne Duplikate und sortiere nach x,y
                unique_points = list(set(story_points))
                if len(unique_points) >= 3:
                    try:
                        # Versuche konvexe Hülle
                        hull = ConvexHull(unique_points)
                        story_area = hull.area
                        print(f"Berechnete Grundfläche aus Wandpunkten: {story_area:.2f}m²")
                    except Exception as e:
                        print(f"Fehler bei Wandflächenberechnung: {e}")
            
            # Methode 3: Grundfläche des ersten Geschosses mit Korrekturfaktor
            if story_area == 0.0 and base_area is not None:
                # Berechne Korrekturfaktor basierend auf der Wandgeometrie
                correction_factor = 1.0
                wall_heights = []
                for wall_points in wall_geometries:
                    z_coords = [p[2] for p in wall_points]
                    if story_bottom <= min(z_coords) <= story_top or story_bottom <= max(z_coords) <= story_top:
                        wall_heights.append(max(z_coords) - min(z_coords))
                
                if wall_heights:
                    # Korrekturfaktor basierend auf Wandhöhen
                    avg_wall_height = sum(wall_heights) / len(wall_heights)
                    correction_factor = avg_wall_height / story_height
                
                story_area = base_area * correction_factor
                print(f"Verwende korrigierte Grundfläche: {story_area:.2f}m² (Faktor: {correction_factor:.2f})")
            
            # Berechne finales Volumen
            if story_area > 0:
                story_volume = story_area * story_height
                print(f"Berechnetes Geschossvolumen: {story_volume:.2f}m³")
            else:
                print("WARNUNG: Konnte keine Grundfläche ermitteln!")
            
            volumes.append(story_volume)
        
        return volumes

    def _analyze_openings(self, wall_surface):
        """Analysiert Öffnungen in einer Wandfläche"""
        openings = []
        
        # Suche nach allen Öffnungen
        for opening_elem in wall_surface.findall('.//bldg:opening', self.ns):
            # Bestimme den Öffnungstyp und hole zusätzliche Attribute
            door = opening_elem.find('.//bldg:Door', self.ns)
            window = opening_elem.find('.//bldg:Window', self.ns)
            
            if door is not None:
                opening_type = 'DOOR'
                function = door.find('.//bldg:function', self.ns)
                function_value = function.text if function is not None else "unbekannt"
            elif window is not None:
                opening_type = 'WINDOW'
                function = window.find('.//bldg:function', self.ns)
                function_value = function.text if function is not None else "unbekannt"
            else:
                opening_type = 'UNKNOWN'
                function_value = "unbekannt"
            
            # Extrahiere Geometrie
            points = self._extract_surface_points(opening_elem)
            if points:
                z_coords = [p[2] for p in points]
                x_coords = [p[0] for p in points]
                y_coords = [p[1] for p in points]
                
                # Berechne Dimensionen
                width = max(x_coords) - min(x_coords)
                height = max(z_coords) - min(z_coords)
                area = self._calculate_opening_area(points)
                
                # Erweiterte Plausibilitätsprüfung
                is_plausible = True
                if opening_type == 'DOOR':
                    if not (1.8 <= height <= 2.5 and 0.7 <= width <= 2.0):
                        is_plausible = False
                        print(f"  WARNUNG: Unplausible Türmaße (B: {width:.2f}m, H: {height:.2f}m)")
                elif opening_type == 'WINDOW':
                    if not (0.5 <= height <= 2.5 and 0.3 <= width <= 3.0):
                        is_plausible = False
                        print(f"  WARNUNG: Unplausible Fenstermaße (B: {width:.2f}m, H: {height:.2f}m)")
                
                if is_plausible:
                    # Berechne Orientierung der Öffnung
                    orientation = self._calculate_opening_orientation(points)
                    
                    opening_info = {
                        'type': opening_type,
                        'function': function_value,
                        'width': width,
                        'height': height,
                        'area': area,
                        'bottom_level': min(z_coords),
                        'top_level': max(z_coords),
                        'center': (
                            (max(x_coords) + min(x_coords)) / 2,
                            (max(y_coords) + min(y_coords)) / 2,
                            (max(z_coords) + min(z_coords)) / 2
                        ),
                        'orientation': orientation
                    }
                    openings.append(opening_info)
        
        return openings

    def _calculate_opening_area(self, points):
        """Berechnet die Fläche einer Öffnung"""
        if len(points) < 3:
            return 0.0
        
        # Berechne Fläche mittels Dreieckszerlegung
        area = 0.0
        n = len(points)
        for i in range(1, n-1):
            # Berechne Kreuzprodukt für Dreieck
            v1 = (
                points[i][0] - points[0][0],
                points[i][1] - points[0][1],
                points[i][2] - points[0][2]
            )
            v2 = (
                points[i+1][0] - points[0][0],
                points[i+1][1] - points[0][1],
                points[i+1][2] - points[0][2]
            )
            # Kreuzprodukt
            cross = (
                v1[1]*v2[2] - v1[2]*v2[1],
                v1[2]*v2[0] - v1[0]*v2[2],
                v1[0]*v2[1] - v1[1]*v2[0]
            )
            # Fläche des Dreiecks
            area += (cross[0]**2 + cross[1]**2 + cross[2]**2)**0.5 / 2
        
        return area

    def _calculate_opening_orientation(self, points):
        """Berechnet die Orientierung einer Öffnung in Grad"""
        if len(points) < 2:
            return 0.0
        
        # Nehme die ersten beiden Punkte für die Richtungsberechnung
        p1, p2 = points[0], points[1]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        
        # Berechne Winkel in Grad (0° = Nord, 90° = Ost, 180° = Süd, 270° = West)
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360
        
        # Ordne in Hauptrichtungen ein
        directions = {
            'N': (0, 22.5),
            'NO': (22.5, 67.5),
            'O': (67.5, 112.5),
            'SO': (112.5, 157.5),
            'S': (157.5, 202.5),
            'SW': (202.5, 247.5),
            'W': (247.5, 292.5),
            'NW': (292.5, 337.5),
            'N2': (337.5, 360)
        }
        
        for direction, (min_angle, max_angle) in directions.items():
            if min_angle <= angle < max_angle:
                return direction if direction != 'N2' else 'N'
        
        return 'N'  # Fallback

    def _calculate_polygon_area(self, points):
        """Berechnet die Fläche eines Polygons in 3D"""
        if len(points) < 3:
            return 0.0
        
        # Projiziere auf XY-Ebene für Flächenberechnung
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        
        return abs(area) / 2.0

def main():
    # Pfad zum Projekt-Root ermitteln
    project_root = Path(__file__).parent.parent.parent
    
    # Pfad zur GML-Datei
    gml_path = project_root / "data" / "citygml" / "099082.gml"
    
    print(f"Versuche Datei zu öffnen: {gml_path}")
    inspector = CityGMLInspector(gml_path)
    inspector.inspect_file()

if __name__ == "__main__":
    main() 
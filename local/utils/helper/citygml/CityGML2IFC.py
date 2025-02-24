import ifcopenshell
from ifcopenshell.api import run
from pathlib import Path
import yaml
import json
import datetime
import geopandas as gpd
from typing import Dict, List, Tuple
from CityGMLInspect import CityGMLInspector
import uuid
import xml.etree.ElementTree as ET

class CityGML2IFC:
    def __init__(self, citygml_path, inspector_results=None):
        """Initialisiert den Konverter mit CityGML Pfad und optionalen Inspektionsergebnissen"""
        self.citygml_path = Path(citygml_path)
        
        # Parse CityGML für Georeferenzierung
        try:
            tree = ET.parse(self.citygml_path)
            self.root = tree.getroot()
            print(f"CityGML-Datei erfolgreich geladen: {self.citygml_path.name}")
        except Exception as e:
            print(f"Warnung: CityGML konnte nicht geladen werden: {str(e)}")
            self.root = None
        
        if inspector_results is None:
            self.inspector = CityGMLInspector(self.citygml_path)
            self.inspector_results = self.inspector.inspect_file()
        else:
            self.inspector = None
            self.inspector_results = inspector_results
        
        self.ifc_file = None
        self.project = None
        self.site = None
        self.model_context = None
        self.body_context = None
        
        # Vereinfachtes Mapping
        self.mapping = {
            'building': {
                'type': 'IfcBuilding',
                'properties': {
                    'height': 'Height',
                    'storeys': 'NumberOfStoreys',
                    'area': 'GrossFloorArea'
                }
            }
        }
        
        self.ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml'
        }

    def _save_metadata(self, metadata_dir: Path, conversion_stats: Dict) -> None:
        """Speichert die Metadaten der Konvertierung"""
        metadata = {
            'source': {
                'file': str(self.citygml_path),
                'format': 'CityGML',
                'version': self.mapping.get('version', 'unknown')
            },
            'conversion': {
                'date': datetime.datetime.now().isoformat(),
                'statistics': conversion_stats,
                'mapping_version': self.mapping.get('version', 'unknown')
            },
            'buildings': {
                'total': conversion_stats['total_buildings'],
                'converted': conversion_stats['successful_conversions'],
                'failed': conversion_stats['failed_conversions'],
                'details': conversion_stats['building_details']
            }
        }
        
        with open(metadata_dir / "citygml_reference.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _save_logs(self, logs_dir: Path, conversion_log: List[Dict], error_log: List[Dict]) -> None:
        """Speichert die Konvertierungs- und Fehlerprotokolle"""
        # Konvertierungsprotokoll
        with open(logs_dir / "conversion_log.yml", 'w', encoding='utf-8') as f:
            yaml.dump(conversion_log, f, allow_unicode=True, default_flow_style=False)
        
        # Fehlerprotokoll
        with open(logs_dir / "error_log.yml", 'w', encoding='utf-8') as f:
            yaml.dump(error_log, f, allow_unicode=True, default_flow_style=False)

    def convert(self, output_path):
        """Konvertiert CityGML-Daten in eine IFC-Datei"""
        try:
            # Erstelle neue IFC-Datei und Basisstruktur
            if not self._create_ifc_base_structure():
                raise Exception("Fehler beim Erstellen der IFC-Basisstruktur")
            
            # Hole Gebäudedaten
            building_data = None
            if self.inspector_results:
                building_data = self.inspector_results  # Verwende übergebene Daten
            elif self.inspector:
                building_data = self.inspector.analyze_building()  # Analysiere neu
            
            if not building_data:
                raise Exception("Keine Gebäudedaten verfügbar")
            
            if isinstance(building_data, (list, tuple)):
                building_data = building_data[0]  # Nimm erstes Gebäude wenn Liste
            
            # Konvertiere Gebäude
            print(f"Konvertiere Gebäude {building_data.get('id', 'unknown')}")
            building = self._convert_building_from_inspection(building_data)
            if building:
                # Speichere IFC-Datei
                self.ifc_file.write(str(output_path))
                return True
            
            return False
        
        except Exception as e:
            print(f"Fehler bei der Konvertierung: {str(e)}")
            return False

    def _convert_building_from_inspection(self, building_data):
        """Konvertiert ein einzelnes Gebäude aus den Inspektionsdaten"""
        try:
            if isinstance(building_data, list):
                building_data = building_data[0]
            
            # Berechne korrekte Geschossfläche
            footprint = building_data.get('footprint', None)
            if footprint and hasattr(footprint, 'area'):
                total_gfa = footprint.area * len(building_data.get('stories', [1]))  # Grundfläche * Anzahl Geschosse
            else:
                total_gfa = building_data.get('area', 0.0)
            
            # Georeferenzierung erstellen
            self._create_georeference(building_data)
            
            # Building-Placement mit korrekter Höhe erstellen
            z_level = building_data.get('ground_level', 0.0)
            if isinstance(z_level, (list, tuple)):
                z_level = z_level[0] if z_level else 0.0
            
            building_placement = self.ifc_file.createIfcLocalPlacement(
                PlacementRelTo=self.site.ObjectPlacement,
                RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                    Location=self.ifc_file.createIfcCartesianPoint([0.0, 0.0, z_level])
                )
            )
            
            # Erstelle Grundrissrepräsentation
            footprint_representation = self._create_footprint_representation(building_data)
            
            # IFC-Gebäude erstellen
            product_shape = None
            if footprint_representation:
                product_shape = self.ifc_file.createIfcProductDefinitionShape(
                    Representations=[footprint_representation]
                )
            
            ifc_building = self.ifc_file.createIfcBuilding(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"Building_{building_data.get('id', 'unknown')}",
                ObjectPlacement=building_placement,
                Representation=product_shape,
                CompositionType="ELEMENT"
            )
            
            # Verknüpfe Building mit Site
            self.ifc_file.createIfcRelAggregates(
                GlobalId=ifcopenshell.guid.new(),
                RelatingObject=self.site,
                RelatedObjects=[ifc_building]
            )

            # Building Properties setzen
            building_props = {
                'NumberOfStoreys': len(building_data.get('stories', [1])),
                'GrossFloorArea': total_gfa,
                'Height': building_data.get('height', 0.0),
                'YearOfConstruction': building_data.get('year_of_construction', None),
                'SpaceCoverage': building_data.get('space_coverage', None)
            }
            self._create_pset(ifc_building, 'Pset_BuildingCommon', building_props)

            # Custom SghP Property Set für WWR
            wwr_props = {
                'wwr_north': building_data.get('wwr_north', 0.0),
                'wwr_east': building_data.get('wwr_east', 0.0),
                'wwr_south': building_data.get('wwr_south', 0.0),
                'wwr_west': building_data.get('wwr_west', 0.0)
            }
            self._create_pset(ifc_building, 'SghP_WindowWallRatios', wwr_props)

            # GFA Space erstellen
            space = self.ifc_file.createIfcSpace(
                GlobalId=ifcopenshell.guid.new(),
                Name="GFA_Total",
                ObjectPlacement=building_placement,
                PredefinedType="GFA"
            )

            # Space räumlich dem Gebäude zuordnen
            self.ifc_file.createIfcRelContainedInSpatialStructure(
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=ifc_building,
                RelatedElements=[space]
            )

            # Space Properties
            space_props = {
                'GrossFloorArea': total_gfa,
                'NetFloorArea': total_gfa * 0.85,  # Annahme: NFA = 85% der GFA
                'IsExternal': False
            }
            self._create_pset(space, 'Pset_SpaceCommon', space_props)

            # Space Quantities
            space_quantities = {
                'GrossFloorArea': total_gfa,
                'NetFloorArea': total_gfa * 0.85,
                'Height': building_data.get('height', 0.0)
            }
            self._create_qto(space, 'Qto_SpaceBaseQuantities', space_quantities)

            return ifc_building

        except Exception as e:
            print(f"Fehler bei der Gebäudekonvertierung: {str(e)}")
            return None

    def _create_georeference(self, building_data):
        """Erstellt die Georeferenzierung für das Projekt basierend auf CityGML-Daten"""
        try:
            if self.root is None:
                return
            
            # EPSG aus CityGML auslesen
            envelope = self.root.find('.//{http://www.opengis.net/gml}Envelope')
            if not envelope:
                return
            
            srs_name = envelope.get('srsName')
            if not srs_name:
                epsg_code = "EPSG:25832"
                epsg_name = "ETRS89 / UTM zone 32N"
            else:
                # Extrahiere EPSG-Code
                if "EPSG" in srs_name:
                    epsg_code = srs_name.split(":")[-1]
                elif "31256" in srs_name:
                    epsg_code = "31256"
                else:
                    epsg_code = srs_name.split(",")[-1].strip() if "," in srs_name else "25832"
                
                epsg_code = f"EPSG:{epsg_code}"
                
                # Mapping für bekannte EPSG-Codes
                epsg_mapping = {
                    "EPSG:25832": "ETRS89 / UTM zone 32N",
                    "EPSG:25833": "ETRS89 / UTM zone 33N",
                    "EPSG:31256": "MGI / Austria GK East",
                }
                epsg_name = epsg_mapping.get(epsg_code, f"Unknown CRS ({epsg_code})")
            
            # Erstelle IfcProjectedCRS
            projected_crs = self.ifc_file.createIfcProjectedCRS(
                Name=epsg_code,
                Description=epsg_name,
                GeodeticDatum="MGI" if epsg_code == "EPSG:31256" else "ETRS89",
                VerticalDatum="Adria" if epsg_code == "EPSG:31256" else "DHHN92",
                MapProjection="GK" if epsg_code == "EPSG:31256" else f"UTM{epsg_code[-2:]}",
                MapZone="East" if epsg_code == "EPSG:31256" else f"{epsg_code[-2:]}N"
            )
            
            # Hole Koordinaten aus building_data
            x = building_data.get('reference_point', {}).get('x', 0.0)
            y = building_data.get('reference_point', {}).get('y', 0.0)
            z = building_data.get('reference_point', {}).get('z', 0.0)
            
            # Erstelle MapConversion
            self.ifc_file.createIfcMapConversion(
                SourceCRS=self.model_context,
                TargetCRS=projected_crs,
                Eastings=float(x),
                Northings=float(y),
                OrthogonalHeight=float(z),
                XAxisAbscissa=1.0,
                XAxisOrdinate=0.0,
                Scale=1.0
            )
            
        except Exception as e:
            pass  # Stille Fehlerbehandlung

    def _create_building_storey(self, ifc_building, story_data, storey_idx):
        """Erstellt ein Geschoss mit korrekter Elevation und Namen"""
        try:
            storey_placement = self.ifc_file.createIfcLocalPlacement(
                PlacementRelTo=ifc_building.ObjectPlacement,
                RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                    Location=self.ifc_file.createIfcCartesianPoint([0.0, 0.0, story_data['bottom_level']])
                )
            )
            
            # Geschoss mit korrektem Namen erstellen
            storey = self.ifc_file.createIfcBuildingStorey(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"BuildingStorey_{storey_idx+1}",
                Description=f"Level {storey_idx+1}",
                ObjectPlacement=storey_placement,
                CompositionType="ELEMENT"
            )
            
            # Mit Gebäude verknüpfen
            self.ifc_file.createIfcRelAggregates(
                GlobalId=ifcopenshell.guid.new(),
                RelatingObject=ifc_building,
                RelatedObjects=[storey]
            )

            # Geschoss-Properties
            storey_props = {
                'GrossPlannedArea': story_data['area'] if 'area' in story_data else 0.0,
                'NetPlannedArea': story_data['area'] * 0.85 if 'area' in story_data else 0.0,
                'ElevationOfSSLRelative': story_data['bottom_level']
            }
            self._create_pset(storey, 'Pset_BuildingStoreyCommon', storey_props)

            return storey

        except Exception as e:
            print(f"Fehler beim Erstellen des Geschosses {storey_idx}: {str(e)}")
            return None

    def _create_gfa_space(self, storey, story_data):
        """Erstellt ein GFA Space im Geschoss"""
        try:
            # GFA Space erstellen
            space = self.ifc_file.createIfcSpace(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"GFA_Space_{storey.Name}",
                ObjectPlacement=storey.ObjectPlacement,
                PredefinedType="GFA"
            )

            # Space räumlich dem Geschoss zuordnen (WICHTIG: IfcRelContainedInSpatialStructure statt IfcRelAggregates)
            self.ifc_file.createIfcRelContainedInSpatialStructure(
                GlobalId=ifcopenshell.guid.new(),
                RelatingStructure=storey,
                RelatedElements=[space]
            )

            # Space Properties
            space_props = {
                'GrossFloorArea': story_data['area'] if 'area' in story_data else 0.0,
                'NetFloorArea': story_data['area'] * 0.85 if 'area' in story_data else 0.0,
                'IsExternal': False
            }
            self._create_pset(space, 'Pset_SpaceCommon', space_props)

            # Space Quantities
            space_quantities = {
                'GrossFloorArea': story_data['area'] if 'area' in story_data else 0.0,
                'NetFloorArea': story_data['area'] * 0.85 if 'area' in story_data else 0.0,
                'Height': story_data['height'] if 'height' in story_data else 0.0
            }
            self._create_qto(space, 'Qto_SpaceBaseQuantities', space_quantities)

            return space

        except Exception as e:
            print(f"Fehler beim Erstellen des GFA Spaces: {str(e)}")
            return None

    def _create_qto(self, entity, qto_name, quantities):
        """Erstellt Quantity Set für eine IFC-Entity"""
        qtos = []
        for name, value in quantities.items():
            if value is not None:
                qto = self.ifc_file.createIfcQuantityArea(
                    Name=name,
                    AreaValue=float(value)
                )
                qtos.append(qto)
        
        if qtos:
            qset = self.ifc_file.createIfcElementQuantity(
                GlobalId=ifcopenshell.guid.new(),
                Name=qto_name,
                Quantities=qtos
            )
            
            self.ifc_file.createIfcRelDefinesByProperties(
                GlobalId=ifcopenshell.guid.new(),
                RelatedObjects=[entity],
                RelatingPropertyDefinition=qset
            )

    def _create_wall(self, story, start_point, end_point, height, wall_idx):
        """Erstellt eine Wand zwischen zwei Punkten"""
        try:
            # Berechne Wandrichtung
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            length = (dx*dx + dy*dy)**0.5
            
            if length < 0.01:  # Ignoriere zu kurze Wände
                return None
            
            # Erstelle Wand-Placement
            wall_placement = self.ifc_file.createIfcLocalPlacement(
                PlacementRelTo=story.ObjectPlacement,
                RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                    Location=self.ifc_file.createIfcCartesianPoint((start_point[0], start_point[1], 0.0)),
                    Axis=self.ifc_file.createIfcDirection((0., 0., 1.)),
                    RefDirection=self.ifc_file.createIfcDirection((dx/length, dy/length, 0.))
                )
            )
            
            # Erstelle IFC-Wand
            wall = self.ifc_file.createIfcWall(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"Wall_{story.Name}_{wall_idx+1}",
                ObjectPlacement=wall_placement
            )
            
            # Erstelle Wandgeometrie
            wall_points = [
                self.ifc_file.createIfcCartesianPoint((0., 0., 0.)),
                self.ifc_file.createIfcCartesianPoint((length, 0., 0.)),
                self.ifc_file.createIfcCartesianPoint((length, 0., height)),
                self.ifc_file.createIfcCartesianPoint((0., 0., height)),
                self.ifc_file.createIfcCartesianPoint((0., 0., 0.))
            ]
            
            # Erstelle geschlossene Polylinie
            polyline = self.ifc_file.createIfcPolyline(wall_points)
            
            # Erstelle Wandprofil
            wall_profile = self.ifc_file.createIfcArbitraryClosedProfileDef(
                "AREA", None, polyline
            )
            
            # Extrudiere Wand
            wall_thickness = 0.3  # 30cm Wandstärke
            extruded_solid = self.ifc_file.createIfcExtrudedAreaSolid(
                wall_profile,
                self.ifc_file.createIfcAxis2Placement3D(
                    self.ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0])
                ),
                self.ifc_file.createIfcDirection((0., 1., 0.)),  # Extrusion in Y-Richtung
                wall_thickness
            )
            
            # Erstelle Wandrepräsentation
            shape_rep = self.ifc_file.createIfcShapeRepresentation(
                self.body_context,
                "Body",
                "SweptSolid",
                [extruded_solid]
            )
            
            # Weise Geometrie der Wand zu
            wall.Representation = self.ifc_file.createIfcProductDefinitionShape(
                None, None, [shape_rep]
            )
            
            return wall
            
        except Exception as e:
            print(f"Fehler beim Erstellen der Wand {wall_idx}: {str(e)}")
            return None

    def _create_ifc_base_structure(self):
        """Erstellt die IFC-Basisstruktur (Project, Site, etc.)"""
        try:
            # IFC4x3 Schema verwenden
            self.ifc_file = ifcopenshell.file(schema="IFC4X3")
            
            # Erstelle Projekt
            self.project = self.ifc_file.createIfcProject(
                GlobalId=ifcopenshell.guid.new(),
                Name="CityGML Conversion Project"
            )
            
            # Erstelle Einheiten
            length_unit = self.ifc_file.createIfcSIUnit(
                UnitType="LENGTHUNIT",
                Name="METRE"
            )
            area_unit = self.ifc_file.createIfcSIUnit(
                UnitType="AREAUNIT",
                Name="SQUARE_METRE"
            )
            units = self.ifc_file.createIfcUnitAssignment([length_unit, area_unit])
            self.project.UnitsInContext = units
            
            # Erstelle geometrischen Kontext
            self.model_context = self.ifc_file.createIfcGeometricRepresentationContext(
                ContextType="Model",
                CoordinateSpaceDimension=3,
                Precision=0.00001,
                WorldCoordinateSystem=self.ifc_file.createIfcAxis2Placement3D(
                    self.ifc_file.createIfcCartesianPoint((0., 0., 0.))
                )
            )
            self.project.RepresentationContexts = [self.model_context]
            
            # Erstelle Footprint-Subkontext für 2D-Geometrien
            self.footprint_context = self.ifc_file.createIfcGeometricRepresentationSubContext(
                ContextIdentifier="Footprint",
                ContextType="Model",
                ParentContext=self.model_context,
                TargetView="PLAN_VIEW"
            )
            
            # Erstelle Site
            site_placement = self.ifc_file.createIfcLocalPlacement(
                RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                    Location=self.ifc_file.createIfcCartesianPoint((0., 0., 0.))
                )
            )
            
            self.site = self.ifc_file.createIfcSite(
                GlobalId=ifcopenshell.guid.new(),
                Name="Site",
                ObjectPlacement=site_placement,
                CompositionType="ELEMENT"
            )
            
            # Verknüpfe Site mit Project
            self.ifc_file.createIfcRelAggregates(
                GlobalId=ifcopenshell.guid.new(),
                RelatingObject=self.project,
                RelatedObjects=[self.site]
            )
            
            return True
            
        except Exception as e:
            print(f"Fehler beim Erstellen der IFC-Basisstruktur: {str(e)}")
            return False

    def _create_footprint_representation(self, building_data):
        """Erstellt eine 2D-Grundrissrepräsentation"""
        try:
            # Extrahiere Grundrisskoordinaten aus building_data
            footprint = building_data.get('footprint', None)
            if footprint and hasattr(footprint, 'exterior'):  # Wenn es ein Shapely Polygon ist
                # Konvertiere Shapely Polygon zu Koordinatenliste
                coords = list(footprint.exterior.coords)
                footprint = [(p[0], p[1]) for p in coords]
            elif not footprint:
                # Fallback: Versuche Grundriss aus CityGML zu extrahieren
                if self.root is not None:
                    building = self.root.find('.//{http://www.opengis.net/citygml/building/1.0}Building')
                    if building is not None:
                        ground_surface = building.find('.//{http://www.opengis.net/citygml/building/1.0}GroundSurface')
                        if ground_surface is not None:
                            pos_list = ground_surface.find('.//{http://www.opengis.net/gml}posList')
                            if pos_list is not None:
                                coords = [float(x) for x in pos_list.text.split()]
                                footprint = [(coords[i], coords[i+1]) for i in range(0, len(coords)-2, 3)]

            if not footprint:
                return None

            # Erstelle IfcPolyline aus den Grundrisspunkten
            points = [self.ifc_file.createIfcCartesianPoint((p[0], p[1])) for p in footprint]
            # Schließe Polygon
            if points[0] != points[-1]:
                points.append(points[0])
            
            polyline = self.ifc_file.createIfcPolyline(points)
            
            # Erstelle Repräsentation
            footprint_representation = self.ifc_file.createIfcShapeRepresentation(
                ContextOfItems=self.footprint_context,
                RepresentationIdentifier="FootPrint",
                RepresentationType="Curve2D",
                Items=[polyline]
            )
            
            return footprint_representation
            
        except Exception as e:
            print(f"Fehler beim Erstellen der Grundrissrepräsentation: {str(e)}")
            return None

    def _extract_geometry_points(self, surface_element):
        """Extrahiert Geometriepunkte aus einem Oberflächenelement"""
        try:
            # Suche nach Geometrie
            pos_list = surface_element.find('.//gml:posList', self.ns)
            if pos_list is not None:
                # Konvertiere String in Liste von Koordinaten
                coords = [float(x) for x in pos_list.text.split()]
                # Gruppiere in 3D-Punkte
                points = [(coords[i], coords[i+1], coords[i+2]) 
                         for i in range(0, len(coords), 3)]
                return points
            
            return None
            
        except Exception as e:
            print(f"Fehler beim Extrahieren der Geometriepunkte: {str(e)}")
            return None

    def _load_mapping(self):
        """Lädt das CityGML zu IFC Mapping aus der YAML-Datei"""
        try:
            import yaml
            mapping_path = Path(__file__) / "mapping" / "citygml_to_ifc.yml"
            
            with open(mapping_path, 'r', encoding='utf-8') as f:
                mapping = yaml.safe_load(f)
                print(f"Mapping-Datei erfolgreich geladen: {mapping_path.name}")
                return mapping
            
        except Exception as e:
            print(f"Fehler beim Laden der Mapping-Datei: {str(e)}")
            raise

    def _create_slab(self, story, footprint, height, is_ground_floor=False):
        """Erstellt eine Geschossdecke oder Bodenplatte"""
        try:
            # Erstelle Decken-Placement relativ zum Geschoss
            slab_placement = self.ifc_file.createIfcLocalPlacement(
                PlacementRelTo=story.ObjectPlacement,
                RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                    Location=self.ifc_file.createIfcCartesianPoint([0.0, 0.0, height if not is_ground_floor else 0.0]),
                    Axis=self.ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
                    RefDirection=self.ifc_file.createIfcDirection([1.0, 0.0, 0.0])
                )
            )

            # Erstelle Deckengeometrie aus Footprint
            points = []
            for coord in footprint.exterior.coords[:-1]:  # Letzter Punkt ist gleich dem ersten
                points.append(
                    self.ifc_file.createIfcCartesianPoint([float(coord[0]), float(coord[1]), 0.0])
                )
            points.append(points[0])  # Schließe die Polylinie
            
            # Erstelle geschlossene Polylinie
            polyline = self.ifc_file.createIfcPolyline(points)
            
            # Erstelle Deckenprofil
            slab_area = self.ifc_file.createIfcArbitraryClosedProfileDef(
                "AREA", None, polyline
            )
            
            # Extrudiere Decke
            thickness = 0.2  # 20cm Deckendicke
            extruded_solid = self.ifc_file.createIfcExtrudedAreaSolid(
                slab_area,
                self.ifc_file.createIfcAxis2Placement3D(
                    self.ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0])
                ),
                self.ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
                thickness
            )
            
            # Erstelle Deckenrepräsentation
            shape_rep = self.ifc_file.createIfcShapeRepresentation(
                self.body_context,
                "Body",
                "SweptSolid",
                [extruded_solid]
            )
            
            # Erstelle IFC-Decke
            slab = self.ifc_file.createIfcSlab(
                GlobalId=ifcopenshell.guid.new(),
                Name=f"{'GroundSlab' if is_ground_floor else 'Slab'}_{story.Name}",
                ObjectPlacement=slab_placement,
                Representation=self.ifc_file.createIfcProductDefinitionShape(
                    None, None, [shape_rep]
                ),
                PredefinedType="BASESLAB" if is_ground_floor else "FLOOR"
            )
            
            return slab
            
        except Exception as e:
            print(f"Fehler beim Erstellen der {'Bodenplatte' if is_ground_floor else 'Geschossdecke'}: {str(e)}")
            return None

    def _create_roof(self, top_story, roof_geometries):
        """Erstellt das Dach und weist es dem obersten Geschoss zu"""
        try:
            for roof_idx, roof_points in enumerate(roof_geometries):
                # Berechne die durchschnittliche Z-Koordinate für die Dachhöhe
                avg_z = sum(p[2] for p in roof_points) / len(roof_points)
                
                # Erstelle Dach-Placement relativ zum obersten Geschoss
                roof_placement = self.ifc_file.createIfcLocalPlacement(
                    PlacementRelTo=top_story.ObjectPlacement,
                    RelativePlacement=self.ifc_file.createIfcAxis2Placement3D(
                        Location=self.ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0]),
                        Axis=self.ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
                        RefDirection=self.ifc_file.createIfcDirection([1.0, 0.0, 0.0])
                    )
                )
                
                # Erstelle Dachgeometrie
                roof_points_ifc = []
                for point in roof_points:
                    # Konvertiere zu relativen Koordinaten
                    relative_x = float(point[0])
                    relative_y = float(point[1])
                    relative_z = float(point[2]) - float(top_story.Elevation)
                    roof_points_ifc.append(
                        self.ifc_file.createIfcCartesianPoint([relative_x, relative_y, relative_z])
                    )
                
                # Schließe die Polylinie
                roof_points_ifc.append(roof_points_ifc[0])
                
                # Erstelle geschlossene Polylinie für die Dachkontur
                polyline = self.ifc_file.createIfcPolyline(roof_points_ifc)
                
                # Erstelle Dachprofil
                roof_area = self.ifc_file.createIfcArbitraryClosedProfileDef(
                    "AREA", None, polyline
                )
                
                # Extrudiere Dach
                thickness = 0.2  # 20cm Dachdicke
                extruded_solid = self.ifc_file.createIfcExtrudedAreaSolid(
                    roof_area,
                    self.ifc_file.createIfcAxis2Placement3D(
                        self.ifc_file.createIfcCartesianPoint([0.0, 0.0, 0.0])
                    ),
                    self.ifc_file.createIfcDirection([0.0, 0.0, 1.0]),
                    thickness
                )
                
                # Erstelle Dachrepräsentation
                shape_rep = self.ifc_file.createIfcShapeRepresentation(
                    self.body_context,
                    "Body",
                    "SweptSolid",
                    [extruded_solid]
                )
                
                # Erstelle IFC-Dach
                roof = self.ifc_file.createIfcRoof(
                    GlobalId=ifcopenshell.guid.new(),
                    Name=f"Roof_{top_story.Name}_{roof_idx+1}",
                    ObjectPlacement=roof_placement,
                    Representation=self.ifc_file.createIfcProductDefinitionShape(
                        None, None, [shape_rep]
                    )
                )
                
                # Weise Dach dem obersten Geschoss zu
                self.ifc_file.createIfcRelContainedInSpatialStructure(
                    GlobalId=ifcopenshell.guid.new(),
                    RelatingStructure=top_story,
                    RelatedElements=[roof]
                )
                
        except Exception as e:
            print(f"Fehler beim Erstellen des Dachs: {str(e)}")

    def _create_pset(self, entity, pset_name, properties):
        """Erstellt Property Set für eine IFC-Entity"""
        try:
            props = []
            for name, value in properties.items():
                if value is not None:
                    # Erstelle die Property mit dem korrekten Datentyp
                    if isinstance(value, bool):
                        prop = self.ifc_file.createIfcPropertySingleValue(
                            Name=name,
                            NominalValue=self.ifc_file.create_entity("IfcBoolean", value)
                        )
                    elif isinstance(value, (int, float)):
                        prop = self.ifc_file.createIfcPropertySingleValue(
                            Name=name,
                            NominalValue=self.ifc_file.create_entity("IfcReal", float(value))
                        )
                    else:
                        prop = self.ifc_file.createIfcPropertySingleValue(
                            Name=name,
                            NominalValue=self.ifc_file.create_entity("IfcText", str(value))
                        )
                    props.append(prop)
            
            if props:
                # Erstelle Property Set
                pset = self.ifc_file.createIfcPropertySet(
                    GlobalId=ifcopenshell.guid.new(),
                    Name=pset_name,
                    HasProperties=props
                )
                
                # Verknüpfe Property Set mit Entity
                self.ifc_file.createIfcRelDefinesByProperties(
                    GlobalId=ifcopenshell.guid.new(),
                    RelatedObjects=[entity],
                    RelatingPropertyDefinition=pset
                )
                
        except Exception as e:
            print(f"Fehler beim Erstellen des Property Sets {pset_name}: {str(e)}")

def main():
    # Pfade definieren
    from pathlib import Path
    import sys
    
    # Füge Projekt-Root zum Python-Path hinzu
    project_root = Path(__file__).parent.parent.parent
    sys.path.append(str(project_root))
    
    input_file = project_root / "data" / "citygml" / "099082.gml"
    output_dir = project_root / "data" / "ifc" / "ifc_buildings"
    output_dir.mkdir(exist_ok=True, parents=True)
    
    try:
        from CityGMLInspect import CityGMLInspector
        
        print(f"Analysiere CityGML Datei: {input_file}")
        
        inspector = CityGMLInspector(input_file)
        inspection_results = inspector.inspect_file()
        
        if inspection_results is None:
            raise ValueError("Keine Analyseergebnisse vom Inspector erhalten")
            
        print(f"Analyseergebnisse: {inspection_results}")
        
        # Konvertiere jedes Gebäude einzeln
        for building_data in inspection_results:
            building_id = building_data['id']
            output_file = output_dir / f"building_{building_id}.ifc"
            
            print(f"\nKonvertiere Gebäude {building_id}")
            converter = CityGML2IFC(input_file, [building_data])  # Nur ein Gebäude übergeben
            success = converter.convert(output_file)
            
            if success:
                print(f"Gebäude {building_id} erfolgreich konvertiert: {output_file}")
            else:
                print(f"Fehler bei der Konvertierung von Gebäude {building_id}")
            
    except Exception as e:
        print(f"Fehler im Hauptprogramm: {str(e)}")
        raise

if __name__ == "__main__":
    main() 
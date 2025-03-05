import os
import sys
from pathlib import Path
import yaml
import pandas as pd
import xml.etree.ElementTree as ET
import logging

# Füge Projekt-Root zum Python-Path hinzu
sys.path.append(str(Path(__file__).parent.parent.parent))

from utils.data_processing.base_building_processor import BaseBuildingProcessor
from utils.data_processing.config_loader import load_config
from utils.data_sources.fetch_wfs_data import ViennaWFS

import uuid
from lxml import etree
import geopandas as gpd
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union

# Konfiguriere Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class CityGMLBuildingProcessor(BaseBuildingProcessor):
    """Verarbeitet Gebäude aus CityGML-Dateien"""
    
    def __init__(self, config: dict):
        """Initialisiert den CityGML Building Processor.
        
        Args:
            config (dict): Die Konfiguration
        """
        super().__init__(config)
        self.citygml_fields = config.get('citygml_fields', {})
        
        # Definiere Namespaces
        self.ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gen': 'http://www.opengis.net/citygml/generics/1.0',
            'gml': 'http://www.opengis.net/gml'
        }
        
    def process_building(self, building: dict) -> dict:
        """Verarbeitet ein einzelnes Gebäude aus CityGML.
        
        Args:
            building (dict): Die Gebäudeinformationen
            
        Returns:
            dict: Die verarbeiteten Gebäudeinformationen
        """
        processed = {
            'building_id': building.get(self.citygml_fields.get('building_id', '@gml:id'), ''),
            'floors_ag': building.get(self.citygml_fields.get('floors_ag', 'numberOfFloorsAboveGround'), 1),
            'floors_bg': 0,  # Standardwert
            'height_ag': building.get(self.citygml_fields.get('height_ag', 'measuredHeight'), 0.0),
            'height_bg': 0.0,  # Standardwert
            'geometry': building.geometry,
            'year': 2020,  # Standardwert
            'standard': '',  # Standardwert
            '1st_use': '',  # Standardwert
            '1st_user': 1.0,  # Standardwert
            '2nd_use': '',  # Standardwert
            '2nd_user': 0.0,  # Standardwert
            '3rd_use': '',  # Standardwert
            '3rd_user': 0.0,  # Standardwert
            'house_no': '',  # Standardwert
            'street': '',  # Standardwert
            'postcode': '',  # Standardwert
            'house_name': '',  # Standardwert
            'resi_type': '',  # Standardwert
            'city': '',  # Standardwert
            'country': ''  # Standardwert
        }
        return processed

    def extract_building_attributes(self, building):
        """Extrahiert alle relevanten Attribute eines Gebäudes"""
        try:
            attributes = {}
            
            # Basis-ID
            gml_id = building.get('{' + self.ns['gml'] + '}id')
            attributes['Name'] = gml_id if gml_id else str(uuid.uuid4())
            
            # Extrahiere CityGML-spezifische Attribute
            for field, xpath in self.citygml_fields.items():
                print(f"\nVersuche Extraktion von {field} mit XPath: {xpath}")
                # Behandle @-Attribute speziell
                if xpath.startswith('@'):
                    attr_name = xpath[1:]  # Entferne das @-Zeichen
                    if ':' in attr_name:  # Behandle Namespace-Präfixe
                        ns, attr = attr_name.split(':')
                        attr_name = '{' + self.ns[ns] + '}' + attr
                    value = building.get(attr_name)
                    print(f"Attribut-Wert für {attr_name}: {value}")
                    attributes[field] = value if value else ""
                else:
                    # Normaler XPath für Elemente
                    element = building.find(f'.//bldg:{xpath}', self.ns)
                    value = ""
                    if element is not None:
                        # Prüfe auf uom-Attribut für Höhe
                        if field == 'height_ag' and element.get('uom') is not None:
                            value = element.text
                        else:
                            value = element.text
                    print(f"Element-Wert für {xpath}: {value}")
                    attributes[field] = value if value else ""
            
            # Versuche verschiedene XPath-Varianten für Stockwerke
            floors_paths = [
                './/bldg:numberOfFloorsAboveGround',
                './/bldg:storeysAboveGround',
                './/bldg:storeys'
            ]
            
            for xpath in floors_paths:
                floors = building.find(xpath, self.ns)
                if floors is not None and floors.text:
                    attributes['floors_ag'] = int(floors.text)
                    break
            
            # Wenn keine Stockwerke gefunden, aus Höhe schätzen
            if 'floors_ag' not in attributes:
                height = building.find('.//bldg:measuredHeight', self.ns)
                if height is not None and height.text:
                    # Schätze Stockwerke (3m pro Stockwerk)
                    estimated_floors = max(1, round(float(height.text) / 3.0))
                    attributes['floors_ag'] = estimated_floors
                    self.logger.info(f"⚠️ Stockwerke geschätzt aus Höhe: {estimated_floors}")
            
            return attributes

        except Exception as e:
            self.logger.error(f"Fehler bei Attributextraktion für Gebäude {attributes.get('Name', 'unbekannt')}: {str(e)}")
            return attributes

    def process_citygml(self, citygml_path):
        """Verarbeitet CityGML und erstellt Basis-GeoDataFrame"""
        try:
            print(f"Verarbeite CityGML: {Path(citygml_path).name}")
            
            # Parse CityGML
            tree = ET.parse(citygml_path)
            root = tree.getroot()
            
            buildings_data = []
            
            # Finde alle Gebäude
            for building in root.findall('.//bldg:Building', self.ns):
                try:
                    # Suche nach dem Grundriss (footprint)
                    footprint = building.find('.//bldg:lod0FootPrint//gml:Polygon', self.ns)
                    if footprint is None:
                        # Fallback: Suche nach anderen Grundriss-Definitionen
                        footprint = building.find('.//bldg:boundedBy//bldg:GroundSurface//gml:Polygon', self.ns)
                    
                    if footprint is not None:
                        # Extrahiere Koordinaten
                        coords = footprint.findall('.//gml:pos', self.ns)
                        if not coords:
                            coords = footprint.findall('.//gml:coordinates', self.ns)
                        
                        if coords:
                            # Konvertiere zu Polygon
                            points = []
                            for coord in coords:
                                x, y, z = map(float, coord.text.split())
                                points.append((x, y))  # Ignoriere z-Koordinate für 2D-Grundriss
                            
                            # Stelle sicher, dass der Polygon geschlossen ist
                            if points[0] != points[-1]:
                                points.append(points[0])
                                
                            polygon = Polygon(points)
                            
                            # Sammle weitere Attribute
                            building_data = {
                                'geometry': polygon,
                                'id': building.get('{http://www.opengis.net/gml}id'),
                                # ... weitere Attribute ...
                            }
                            buildings_data.append(building_data)
                
                except Exception as e:
                    self.logger.warning(f"⚠️ Fehler bei Gebäude {building.get('{http://www.opengis.net/gml}id')}: {str(e)}")
                    continue
            
            # Erstelle GeoDataFrame
            buildings_gdf = gpd.GeoDataFrame(buildings_data, crs=self.config['crs'])
            
            # Validiere Geometrien
            invalid_geoms = buildings_gdf[~buildings_gdf.geometry.is_valid]
            if not invalid_geoms.empty:
                self.logger.warning(f"⚠️ {len(invalid_geoms)} ungültige Geometrien gefunden, versuche Reparatur...")
                buildings_gdf.geometry = buildings_gdf.geometry.buffer(0)
            
            self.logger.info(f"✅ {len(buildings_gdf)} Gebäudegrundrisse extrahiert")
            return buildings_gdf

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
            raise

    def create_buildings_dataframe(self, citygml_path):
        """Erstellt DataFrame aus CityGML"""
        try:
            tree = etree.parse(citygml_path)
            root = tree.getroot()
            
            buildings_data = []
            geometries = []
            
            for building in root.findall('.//bldg:Building', self.ns):
                # Erst Geometrie extrahieren
                footprint = self.extract_building_footprint(building)
                if isinstance(footprint, Point):
                    self.logger.warning(f"Keine gültige Geometrie für Gebäude gefunden, überspringe...")
                    continue
                
                # Dann Attribute extrahieren
                building_data = self.extract_building_attributes(building)
                buildings_data.append(building_data)
                geometries.append(footprint)
            
            # Erstelle GeoDataFrame nur wenn Daten vorhanden
            if buildings_data:
                # Erstelle erst DataFrame
                df = pd.DataFrame(buildings_data)
                
                # Konvertiere zu GeoDataFrame
                buildings_gdf = gpd.GeoDataFrame(
                    df,
                    geometry=geometries,
                    crs="EPSG:31256"  # MGI/Austria GK East
                )
                
                # Reichere mit WFS-Daten an
                buildings_gdf = self.enrich_with_wfs(buildings_gdf)
                
                self.logger.info(f"GeoDataFrame erstellt mit {len(buildings_gdf)} Gebäuden")
                return buildings_gdf
            else:
                self.logger.warning("Keine Gebäude in CityGML gefunden")
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")  # Leerer GeoDataFrame
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen des DataFrames: {str(e)}")
            raise
        
    def extract_building_footprint(self, building):
        """Extrahiert die Grundrissgeometrie aus bldg:lod2MultiSurface"""
        try:
            building_id = building.get('{' + self.ns['gml'] + '}id', 'unknown')
            geometries = []
            
            # Suche nach lod2MultiSurface
            surfaces = building.findall('.//bldg:lod2MultiSurface//gml:posList', self.ns)
            
            if not surfaces:
                print(f"⚠️ Kein lod2MultiSurface für Gebäude {building_id}")
                return None

            for surface in surfaces:
                coords = self._extract_surface_points(surface.text)
                if coords and len(coords) >= 3:
                    poly = Polygon(coords)
                    if poly.is_valid:
                        geometries.append(poly)

            if not geometries:
                print(f"❌ Keine gültigen Polygone für Gebäude {building_id}")
                return None

            # Kombiniere alle Flächen, falls mehrere vorhanden sind
            combined = unary_union(geometries)
            if combined.is_valid:
                return combined
            else:
                print(f"⚠️ Vereinigte Geometrie für Gebäude {building_id} ist ungültig")
                return geometries[0]  # Fallback: Erste gültige Geometrie
            
        except Exception as e:
            print(f"❌ Fehler bei der Geometrie-Extraktion für Gebäude {building_id}: {str(e)}")
            return None


    def _extract_surface_points(self, coords_text):
        """Konvertiert 3D-Koordinaten in 2D-Koordinaten (ignoriere Z-Werte)"""
        try:
            coords = [float(x) for x in coords_text.split()]
            
            if len(coords) % 3 == 0:  # 3D-Koordinaten (X, Y, Z)
                coords = [(coords[i], coords[i+1]) for i in range(0, len(coords), 3)]
            elif len(coords) % 2 == 0:  # Falls doch 2D-Koordinaten (X, Y)
                coords = [(coords[i], coords[i+1]) for i in range(0, len(coords), 2)]
            else:
                print(f"❌ Fehler: Unerwartetes Koordinatenformat: {coords_text}")
                return None

            # Stelle sicher, dass das Polygon geschlossen ist
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            return coords
        except Exception as e:
            print(f"❌ Fehler bei _extract_surface_points: {str(e)}")
            return None

    def enrich_with_wfs(self, buildings_gdf):
        """Reichert GeoDataFrame mit WFS-Daten an"""
        try:
            wfs = ViennaWFS()
            enriched_data = wfs.enrich_buildings(buildings_gdf)
            self.logger.info("✅ WFS-Anreicherung abgeschlossen")
            return enriched_data
        except Exception as e:
            self.logger.error(f"❌ Fehler bei WFS-Anreicherung: {str(e)}")
            return buildings_gdf


def fetch_citygml_buildings(citygml_path: Path, config: dict, cea_config: dict, logger=None) -> gpd.GeoDataFrame:
    """Verarbeitet CityGML-Datei und erstellt CEA-kompatible Dateien"""
    try:
        if logger is None:
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.INFO)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)

        # Initialisiere Processor
        processor = CityGMLBuildingProcessor(config)
        
        # Verarbeite CityGML
        buildings_gdf = processor.create_buildings_dataframe(citygml_path)
        
        if buildings_gdf.empty:
            logger.warning("Keine Gebäude in der CityGML-Datei gefunden")
            return None
        
        logger.info(f"📊 Gefundene Gebäude: {len(buildings_gdf)}")
        
        # Reichere mit WFS-Daten an
        buildings_gdf = processor.enrich_with_wfs(buildings_gdf)
        logger.info("✅ WFS-Anreicherung abgeschlossen")
        
        return buildings_gdf
        
    except Exception as e:
        if logger:
            logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
        print(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
        raise

def main():
    """Test-Ausführung"""
    try:
        print("🔍 CityGML Daten Test-Modus")

        # Lade Konfiguration
        config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "data_sources" / "vienna_citygml_normalized.yml"
        print(f"📂 Lade Konfiguration: {config_path.name}")
        citygml_config = load_config(config_path)

        # Test-Datei
        test_file = Path(__file__).resolve().parent.parent.parent / "data" / "citygml" / "099082.gml"
        print(f"\n📂 Verarbeite CityGML: {test_file.name}")

        if not test_file.exists():
            print(f"❌ Test-Datei nicht gefunden: {test_file}")
            return

        # CityGML Verarbeiten
        processor = CityGMLBuildingProcessor(citygml_config)
        data = processor.process_citygml(test_file)

        if data is not None and not data.empty:
            print("\n✅ CityGML Daten erfolgreich geladen:")
            print(f"🏠 Anzahl Gebäude: {len(data)}")
            print(f"📊 Verfügbare Spalten: {', '.join(data.columns)}")

            # Zeige Beispieldaten
            print("\n🔹 Beispieldaten (erste Zeile):")
            print(data.iloc[0])
        else:
            print("❌ Keine Gebäude geladen")

    except Exception as e:
        print(f"❌ Fehler im Test-Modus: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
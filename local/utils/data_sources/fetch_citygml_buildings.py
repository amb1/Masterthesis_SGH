import os
import sys
from pathlib import Path
import yaml
import pandas as pd

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

class CityGMLBuildingProcessor(BaseBuildingProcessor):
    """CityGML-spezifische Verarbeitung"""
    def __init__(self, config, cea_config=None):
        super().__init__(config, cea_config)  
        self.citygml_mapping = config.get("citygml_fields", {})
        self.building_type_mapping = config.get("building_type_mapping", {})
        self.usage_type_mapping = config.get("usage_type_mapping", {})
        self.ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gen': 'http://www.opengis.net/citygml/generics/1.0',
            'gml': 'http://www.opengis.net/gml'
        }

    def extract_building_attributes(self, building):
        """Extrahiert alle relevanten Attribute eines Gebäudes"""
        try:
            attributes = {}
            
            # Basis-ID
            gml_id = building.get('{' + self.ns['gml'] + '}id')
            attributes['Name'] = gml_id if gml_id else str(uuid.uuid4())
            
            # Extrahiere CityGML-spezifische Attribute
            for field, xpath in self.citygml_mapping.items():
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
            
            return attributes

        except Exception as e:
            self.logger.error(f"Fehler bei Attributextraktion für Gebäude {attributes.get('Name', 'unbekannt')}: {str(e)}")
            return attributes

    def process_citygml(self, citygml_path):
        """Verarbeitet CityGML und erstellt Basis-GeoDataFrame"""
        try:
            print(f"Verarbeite CityGML: {Path(citygml_path).name}")
            
            # Parse CityGML
            tree = etree.parse(citygml_path)
            root = tree.getroot()
            
            buildings = root.findall('.//bldg:Building', self.ns)
            print(f"\n=== Starte Verarbeitung von {len(buildings)} Gebäuden ===")
            
            building_data = []
            geometries = []
            geometry_stats = {
                'success': 0,
                'failed': 0,
                'total_area': 0,
                'min_area': float('inf'),
                'max_area': 0
            }
            
            for building in buildings:
                # Erst Geometrie extrahieren
                footprint = self.extract_building_footprint(building)
                if footprint:
                    area = footprint.area
                    geometry_stats['success'] += 1
                    geometry_stats['total_area'] += area
                    geometry_stats['min_area'] = min(geometry_stats['min_area'], area)
                    geometry_stats['max_area'] = max(geometry_stats['max_area'], area)
                else:
                    geometry_stats['failed'] += 1
                    continue
                
                # Dann Attribute extrahieren
                building_data.append(self.extract_building_attributes(building))
                geometries.append(footprint)

            # Ausgabe der Geometrie-Statistiken
            print("\n=== Geometrie-Verarbeitung Zusammenfassung ===")
            print(f"Erfolgreich: {geometry_stats['success']} Gebäude")
            print(f"Fehlgeschlagen: {geometry_stats['failed']} Gebäude")
            if geometry_stats['success'] > 0:
                avg_area = geometry_stats['total_area'] / geometry_stats['success']
                print(f"Durchschnittliche Grundfläche: {avg_area:.1f}m²")
                print(f"Kleinste Grundfläche: {geometry_stats['min_area']:.1f}m²")
                print(f"Größte Grundfläche: {geometry_stats['max_area']:.1f}m²")
            
            # Erstelle GeoDataFrame
            buildings_gdf = gpd.GeoDataFrame(
                building_data,
                geometry=geometries,
                crs="EPSG:31256"
            )
            
            return buildings_gdf
            
        except Exception as e:
            print(f"❌ Fehler bei CityGML-Verarbeitung: {str(e)}")
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


def fetch_citygml_buildings(citygml_path, config, cea_config):
    """Lädt und verarbeitet CityGML Gebäudedaten"""
    try:
        processor = CityGMLBuildingProcessor(config, cea_config)
        buildings_df = processor.process_citygml(citygml_path)
        return buildings_df
    except Exception as e:
        print(f"Fehler beim Verarbeiten der CityGML Daten: {str(e)}")
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
        processor = CityGMLBuildingProcessor(citygml_config, cea_config)
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
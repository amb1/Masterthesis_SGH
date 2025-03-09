import unittest
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import yaml
import logging
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime

# Füge das lokale Verzeichnis zum Python-Path hinzu
local_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(local_dir))

from utils.data_processing.project_structure_manager import ProjectStructureManager
from utils.data_processing.create_site_polygon import create_site_polygon
from utils.data_processing.config_loader import load_config
from utils.data_sources.fetch_citygml_buildings import CityGMLBuildingProcessor

class TestCEAWorkflow(unittest.TestCase):
    """Testklasse für den CEA-Workflow"""
    
    @classmethod
    def setUpClass(cls):
        """Initialisiere Testumgebung"""
        # Lade Konfigurationen
        cls.config = load_config(local_dir / "cfg" / "project_config.yml")
        cls.cea_config = load_config(local_dir / "cfg" / "cea_config.yml")
        
        # Erstelle Testverzeichnisse
        cls.test_project = "test_project"
        cls.test_scenario = "test_scenario"
        cls.project_path = Path("projects") / cls.test_project
        cls.scenario_path = cls.project_path / cls.test_scenario
        
        # Initialisiere ProjectStructureManager
        cls.structure_manager = ProjectStructureManager(cls.config)
        
        # Erstelle Test-Geometrie
        cls.test_polygon = Polygon([
            (0, 0), (0, 100), (100, 100), (100, 0), (0, 0)
        ])
        cls.test_gdf = gpd.GeoDataFrame(
            {'geometry': [cls.test_polygon]},
            crs="EPSG:31256"
        )
        
        # Konfiguriere Logging
        logging.basicConfig(level=logging.INFO)
        cls.logger = logging.getLogger(__name__)

    def setUp(self):
        """Vorbereitung für jeden Test"""
        # Erstelle Projektstruktur
        self.structure_manager.setup_project_structure(
            self.project_path,
            self.scenario_path
        )

    def tearDown(self):
        """Aufräumen nach jedem Test"""
        # Lösche Testverzeichnisse
        if self.scenario_path.exists():
            for file in self.scenario_path.rglob('*'):
                if file.is_file():
                    file.unlink()
            for dir in reversed(list(self.scenario_path.rglob('*'))):
                if dir.is_dir():
                    dir.rmdir()
            self.scenario_path.rmdir()
        if self.project_path.exists():
            self.project_path.rmdir()

    def test_project_structure(self):
        """Test der Projektstruktur"""
        # Überprüfe ob Verzeichnisse existieren
        self.assertTrue(self.scenario_path.exists())
        self.assertTrue((self.scenario_path / 'inputs').exists())
        self.assertTrue((self.scenario_path / 'outputs').exists())
        
        # Überprüfe ob Dateien existieren
        required_files = [
            'inputs/building-geometry/zone.shp',
            'inputs/building-geometry/site.shp',
            'inputs/building-geometry/surroundings.shp',
            'inputs/building-properties/typology.dbf',
            'inputs/networks/streets.shp'
        ]
        
        for file_path in required_files:
            self.assertTrue((self.scenario_path / file_path).exists())

    def test_site_polygon_creation(self):
        """Test der Site-Polygon Erstellung"""
        # Erstelle Site-Polygon
        site_gdf = create_site_polygon(self.test_gdf)
        
        # Überprüfe Eigenschaften
        self.assertIsInstance(site_gdf, gpd.GeoDataFrame)
        self.assertEqual(len(site_gdf), 1)
        self.assertTrue('Name' in site_gdf.columns)
        self.assertEqual(site_gdf['Name'].iloc[0], 'Site')

    def test_config_loading(self):
        """Test des Konfigurationsladens"""
        # Überprüfe Projekt-Konfiguration
        self.assertIsInstance(self.config, dict)
        self.assertTrue('project' in self.config)
        self.assertTrue('data_source' in self.config)
        
        # Überprüfe CEA-Konfiguration
        self.assertIsInstance(self.cea_config, dict)
        self.assertTrue('paths' in self.cea_config)
        self.assertTrue('cea_settings' in self.cea_config)

    def test_citygml_processing(self):
        """Test der CityGML-Verarbeitung mit verschiedenen Szenarien"""
        # Verwende die echte CityGML-Datei
        citygml_path = local_dir / "data" / "citygml" / "099082.gml"
        self.assertTrue(citygml_path.exists(), f"CityGML-Datei nicht gefunden: {citygml_path}")
        
        # Debug: Dateigröße und Inhalt
        print(f"\nDateigröße: {citygml_path.stat().st_size / (1024*1024):.2f} MB")
        
        # Initialisiere Processor
        processor = CityGMLBuildingProcessor(self.config)
        
        # Debug: Namespaces
        print(f"\nKonfigurierte Namespaces: {processor.ns}")
        
        # Test 1: Basis-Verarbeitung
        buildings_gdf = processor.process_citygml(citygml_path)
        
        # Debug: Ergebnis
        if buildings_gdf is None:
            print("\nKeine Gebäude gefunden. Mögliche Gründe:")
            print("1. Namespace-Konfiguration falsch")
            print("2. Geometrie-Extraktion fehlgeschlagen")
            print("3. Attribut-Extraktion fehlgeschlagen")
        else:
            print(f"\nGefundene Gebäude: {len(buildings_gdf)}")
            print(f"Spalten: {buildings_gdf.columns.tolist()}")
        
        # Überprüfe Basis-Ergebnisse
        self.assertIsNotNone(buildings_gdf)
        self.assertFalse(buildings_gdf.empty)
        self.assertTrue('geometry' in buildings_gdf.columns)
        self.assertTrue('height' in buildings_gdf.columns)
        self.assertTrue('year' in buildings_gdf.columns)
        self.assertTrue('type' in buildings_gdf.columns)
        self.assertTrue('use' in buildings_gdf.columns)
        
        # Test 2: Geometrie-Validierung
        self.assertTrue(all(buildings_gdf.geometry.is_valid))
        self.assertTrue(all(buildings_gdf.geometry.type == 'Polygon'))
        
        # Test 3: Wertebereiche
        self.assertTrue(all(buildings_gdf['height'] > 0))
        self.assertTrue(all((buildings_gdf['year'] >= 1800) & (buildings_gdf['year'] <= datetime.now().year)))
        
        # Test 4: Attribut-Extraktion
        for _, building in buildings_gdf.iterrows():
            self.assertIsNotNone(building['height'])
            self.assertIsNotNone(building['year'])
            self.assertIsNotNone(building['type'])
            self.assertIsNotNone(building['use'])
            
        # Test 5: CRS-Konvertierung
        self.assertEqual(buildings_gdf.crs, "EPSG:31256")
        
        # Test 6: Datenqualität
        self.assertGreater(len(buildings_gdf), 0, "Keine Gebäude gefunden")
        self.assertLess(len(buildings_gdf), 1000, "Unrealistisch viele Gebäude gefunden")
        
        # Test 7: Attributwerte
        valid_types = {'MFH', 'SFH', 'OFFICE', 'INDUSTRIAL', 'COMMERCIAL', 'EDUCATION', 'HEALTH', 'OTHER'}
        self.assertTrue(all(building['type'] in valid_types for _, building in buildings_gdf.iterrows()))
        
        valid_uses = {'MULTI_RES', 'SINGLE_RES', 'OFFICE', 'INDUSTRIAL', 'COMMERCIAL', 'EDUCATION', 'HEALTH', 'OTHER'}
        self.assertTrue(all(building['use'] in valid_uses for _, building in buildings_gdf.iterrows()))
        
        # Test 8: Building Parts
        building_parts = buildings_gdf[buildings_gdf['type'] == 'BUILDING_PART']
        if not building_parts.empty:
            print(f"\nGefundene Building Parts: {len(building_parts)}")
            # Überprüfe, ob Building Parts korrekt verarbeitet wurden
            self.assertTrue(all(building_parts['parent_id'].notna()))
            self.assertTrue(all(building_parts['geometry'].is_valid))
            
        # Test 9: Verschiedene Geometrietypen
        geometry_types = buildings_gdf.geometry.type.unique()
        print(f"\nGefundene Geometrietypen: {geometry_types}")
        self.assertTrue('Polygon' in geometry_types)
        
        # Test 10: Namespace-Handling
        version = get_citygml_version(citygml_path)
        print(f"\nCityGML-Version: {version}")
        if version == '1.0':
            self.assertTrue('bldg' in processor.ns and '1.0' in processor.ns['bldg'])
        elif version == '2.0':
            self.assertTrue('bldg' in processor.ns and '2.0' in processor.ns['bldg'])
        elif version == '3.0':
            self.assertTrue('bldg' in processor.ns and '3.0' in processor.ns['bldg'])
            
        # Test 11: Geometrie-Extraktion
        for _, building in buildings_gdf.iterrows():
            # Überprüfe, ob die Geometrie korrekt extrahiert wurde
            self.assertTrue(building['geometry'].is_valid)
            self.assertTrue(building['geometry'].area > 0)
            self.assertTrue(building['geometry'].length > 0)
            
        # Test 12: Attribut-Mapping
        for _, building in buildings_gdf.iterrows():
            # Überprüfe, ob die Attribute korrekt gemappt wurden
            self.assertIsNotNone(building['type'])
            self.assertIsNotNone(building['use'])
            self.assertIsNotNone(building['height'])
            self.assertIsNotNone(building['year'])
            
        # Test 13: Datenkonsistenz
        # Überprüfe, ob die Höhenangaben realistisch sind
        self.assertTrue(all(buildings_gdf['height'] <= 300))  # Maximal 300m Höhe
        # Überprüfe, ob die Flächenangaben realistisch sind
        self.assertTrue(all(buildings_gdf['geometry'].area <= 100000))  # Maximal 100.000m²

if __name__ == '__main__':
    unittest.main() 
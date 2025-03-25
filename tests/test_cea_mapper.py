import unittest
import os
from pathlib import Path
import yaml
from pipeline.processing.cea_mapper import CEAMapper

class TestCEAMapper(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Test-Konfiguration erstellen"""
        cls.test_config = {
            "cea_mappings": {
                "zone": {
                    "Name": {
                        "sources": {
                            "wfs": {
                                "street": "Gebäudeinfo_STRNAML",
                                "number": "Gebäudeinfo_VONN"
                            },
                            "format": "{street}_{number}"
                        }
                    },
                    "floors_bg": {
                        "default": 1
                    },
                    "usage": {
                        "sources": {
                            "wfs": ["Gebäudeinfo_L_NUTZUNG", "Realnutzung_NUTZUNG_LEVEL1"]
                        }
                    }
                }
            }
        }
        
        # Temporäre Konfig-Datei erstellen
        cls.config_path = Path("tests/test_config.yml")
        with open(cls.config_path, "w", encoding="utf-8") as f:
            yaml.dump(cls.test_config, f)
            
    def setUp(self):
        """Mapper für jeden Test initialisieren"""
        self.mapper = CEAMapper(str(self.config_path))
        
    def test_config_loading(self):
        """Test: Konfiguration wird korrekt geladen"""
        self.assertIsNotNone(self.mapper.config)
        self.assertIn("cea_mappings", self.mapper.config)
        self.assertIn("zone", self.mapper.config["cea_mappings"])
        
    def test_get_value_default(self):
        """Test: Default-Wert wird korrekt zurückgegeben"""
        field_config = self.mapper.config["cea_mappings"]["zone"]["floors_bg"]
        value = self.mapper._get_value({}, field_config)
        self.assertEqual(value, "1")
        
    def test_get_value_formatted(self):
        """Test: Formatierte Werte werden korrekt zusammengesetzt"""
        data = {
            "Gebäudeinfo_STRNAML": "Teststraße",
            "Gebäudeinfo_VONN": "42"
        }
        field_config = self.mapper.config["cea_mappings"]["zone"]["Name"]
        value = self.mapper._get_value(data, field_config)
        self.assertEqual(value, "Teststraße_42")
        
    def test_get_value_multiple_sources(self):
        """Test: Mehrere Quellen werden korrekt geprüft"""
        data = {
            "Realnutzung_NUTZUNG_LEVEL1": "Wohngebäude"
        }
        field_config = self.mapper.config["cea_mappings"]["zone"]["usage"]
        value = self.mapper._get_value(data, field_config)
        self.assertEqual(value, "Wohngebäude")
        
        # Test mit erster Quelle
        data = {
            "Gebäudeinfo_L_NUTZUNG": "Bürogebäude",
            "Realnutzung_NUTZUNG_LEVEL1": "Wohngebäude"
        }
        value = self.mapper._get_value(data, field_config)
        self.assertEqual(value, "Bürogebäude")
        
    def test_get_floors_ag(self):
        """Test: Stockwerksberechnung über Grund"""
        # Test mit direkter Stockwerksangabe
        data = {"GEBAEUDEINFOOGD_GESCH_ANZ": "4"}
        self.assertEqual(self.mapper._get_floors_ag(data), 4)
        
        # Test mit Höhenberechnung
        data = {"measuredHeight": "15.0"}
        self.assertEqual(self.mapper._get_floors_ag(data), 5)
        
        # Test mit Fallback
        data = {}
        self.assertEqual(self.mapper._get_floors_ag(data), 1)
        
    def test_get_height_ag(self):
        """Test: Höhenberechnung über Grund"""
        # Test mit measuredHeight
        data = {"measuredHeight": "15.0"}
        self.assertEqual(self.mapper._get_height_ag(data), 15.0)
        
        # Test mit HoeheDach
        data = {"HoeheDach": "12.5"}
        self.assertEqual(self.mapper._get_height_ag(data), 12.5)
        
        # Test mit Stockwerksberechnung
        data = {"GEBAEUDEINFOOGD_GESCH_ANZ": "4"}
        self.assertEqual(self.mapper._get_height_ag(data), 12.0)
        
        # Test mit Fallback
        data = {}
        self.assertEqual(self.mapper._get_height_ag(data), 3.0)
        
    @classmethod
    def tearDownClass(cls):
        """Aufräumen nach den Tests"""
        if cls.config_path.exists():
            cls.config_path.unlink()

if __name__ == "__main__":
    unittest.main() 
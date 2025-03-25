import unittest
from pipeline.processing.building_classifier import BuildingClassifier

class TestBuildingClassifier(unittest.TestCase):
    
    def setUp(self):
        """Classifier für jeden Test initialisieren"""
        self.classifier = BuildingClassifier()
        
    def test_get_building_period(self):
        """Test: Bauperioden werden korrekt ermittelt"""
        # Test für verschiedene Perioden
        self.assertEqual(self.classifier.get_building_period(1900), "I")
        self.assertEqual(self.classifier.get_building_period(1930), "II")
        self.assertEqual(self.classifier.get_building_period(1960), "III")
        self.assertEqual(self.classifier.get_building_period(1980), "IV")
        self.assertEqual(self.classifier.get_building_period(2000), "V")
        self.assertEqual(self.classifier.get_building_period(2020), "VI")
        
        # Test für Grenzfälle
        self.assertEqual(self.classifier.get_building_period(1918), "I")
        self.assertEqual(self.classifier.get_building_period(1919), "II")
        
        # Test für None
        self.assertEqual(self.classifier.get_building_period(None), "III")
        
    def test_get_building_type(self):
        """Test: Gebäudetypen werden korrekt ermittelt"""
        # Test für verschiedene Typen
        self.assertEqual(self.classifier.get_building_type("Mehrfamilienhaus"), "MULTI_RES")
        self.assertEqual(self.classifier.get_building_type("Einfamilienhaus"), "SINGLE_RES")
        self.assertEqual(self.classifier.get_building_type("Bürogebäude"), "OFFICE")
        self.assertEqual(self.classifier.get_building_type("Industriegebäude"), "INDUSTRIAL")
        self.assertEqual(self.classifier.get_building_type("Einzelhandel"), "RETAIL")
        self.assertEqual(self.classifier.get_building_type("Schule"), "SCHOOL")
        self.assertEqual(self.classifier.get_building_type("Restaurant"), "RESTAURANT")
        self.assertEqual(self.classifier.get_building_type("Mischnutzung"), "MULTI_USE")
        
        # Test für Teilübereinstimmungen
        self.assertEqual(self.classifier.get_building_type("Großes Bürogebäude"), "OFFICE")
        self.assertEqual(self.classifier.get_building_type("Altes Wohngebäude"), "MULTI_RES")
        
        # Test für unbekannte Nutzung
        self.assertEqual(self.classifier.get_building_type(None), "MULTI_RES")
        self.assertEqual(self.classifier.get_building_type(""), "MULTI_RES")
        self.assertEqual(self.classifier.get_building_type("Unbekannt"), "MULTI_RES")
        
    def test_get_standard(self):
        """Test: Gebäudestandard wird korrekt ermittelt"""
        # Test für vollständige Daten
        data = {
            "Gebäudeinfo_BAUJAHR": "1960",
            "Gebäudeinfo_L_NUTZUNG": "Bürogebäude"
        }
        self.assertEqual(self.classifier.get_standard(data), "OFFICE_III")
        
        # Test für alternative Nutzungsquelle
        data = {
            "Gebäudeinfo_BAUJAHR": "2000",
            "Realnutzung_NUTZUNG_LEVEL1": "Wohngebäude"
        }
        self.assertEqual(self.classifier.get_standard(data), "MULTI_RES_V")
        
        # Test für fehlende Daten
        data = {}
        self.assertEqual(self.classifier.get_standard(data), "MULTI_RES_III")
        
        # Test für ungültiges Baujahr
        data = {
            "Gebäudeinfo_BAUJAHR": "nicht_numerisch",
            "Gebäudeinfo_L_NUTZUNG": "Bürogebäude"
        }
        self.assertEqual(self.classifier.get_standard(data), "OFFICE_III")

if __name__ == "__main__":
    unittest.main() 
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

class CityGMLAnalyzer:
    def __init__(self, citygml_path: Path):
        self.citygml_path = Path(citygml_path)
        self.ns = {
            'core': 'http://www.opengis.net/citygml/1.0',
            'bldg': 'http://www.opengis.net/citygml/building/1.0',
            'gml': 'http://www.opengis.net/gml'
        }
        
    def analyze_parameters(self):
        """Analysiert alle Parameter der Gebäude in der CityGML-Datei"""
        try:
            print(f"\nAnalysiere CityGML-Datei: {self.citygml_path.name}")
            
            # Parse XML
            tree = ET.parse(str(self.citygml_path))
            root = tree.getroot()
            
            # Sammle Parameter und Werte
            parameters = defaultdict(set)
            building_count = 0
            
            # Suche alle Gebäude
            for building in root.findall('.//bldg:Building', self.ns):
                building_count += 1
                
                # Rekursiv alle Attribute und deren Werte sammeln
                self._collect_parameters(building, parameters)
            
            # Ausgabe der Ergebnisse
            print(f"\nGefundene Gebäude: {building_count}")
            print("\n=== Verfügbare Parameter ===")
            
            for param, values in sorted(parameters.items()):
                print(f"\n{param}:")
                print(f"- Anzahl unique Werte: {len(values)}")
                print("- Beispielwerte (max. 5):", list(values)[:5])
                
        except Exception as e:
            print(f"Fehler bei der Analyse: {str(e)}")
            raise
            
    def _collect_parameters(self, element, parameters, parent_path=""):
        """Sammelt rekursiv alle Parameter und deren Werte"""
        # Element-Name ohne Namespace
        tag = element.tag.split('}')[-1]
        current_path = f"{parent_path}/{tag}" if parent_path else tag
        
        # Attribute sammeln
        for key, value in element.attrib.items():
            # Entferne Namespace aus Attributnamen
            key = key.split('}')[-1]
            param_path = f"{current_path}/@{key}"
            parameters[param_path].add(value)
        
        # Text-Inhalt sammeln
        if element.text and element.text.strip():
            parameters[current_path].add(element.text.strip())
        
        # Rekursiv für alle Kindelemente
        for child in element:
            self._collect_parameters(child, parameters, current_path)

def main():
    # Eingabe der Datei
    citygml_path = input("Bitte Pfad zur CityGML-Datei eingeben: ")
    
    # Analyse durchführen
    analyzer = CityGMLAnalyzer(Path(citygml_path))
    analyzer.analyze_parameters()

if __name__ == "__main__":
    main() 
import ifcopenshell
import numpy as np
from typing import Dict, List, Tuple

class IFCBuildingAnalyzer:
    def __init__(self, ifc_file_path: str):
        self.ifc_file = ifcopenshell.open(ifc_file_path)
        
    def analyze_building(self):
        """Hauptanalyse-Funktion"""
        windows = self.ifc_file.by_type("IfcWindow")
        walls = self.ifc_file.by_type("IfcWall")
        
        analysis = {
            "Nord": {"walls": [], "windows": [], "wall_area": 0, "window_area": 0},
            "Ost": {"walls": [], "windows": [], "wall_area": 0, "window_area": 0},
            "Süd": {"walls": [], "windows": [], "wall_area": 0, "window_area": 0},
            "West": {"walls": [], "windows": [], "wall_area": 0, "window_area": 0},
            "Unbestimmt": {"walls": [], "windows": [], "wall_area": 0, "window_area": 0}
        }
        
        # Wände analysieren
        print("\nAnalysiere Wände...")
        for wall in walls:
            orientation = self._get_wall_orientation(wall)
            wall_data = self._get_wall_data(wall)
            analysis[orientation]["walls"].append(wall_data)
            
            if wall_data["area"]:
                analysis[orientation]["wall_area"] += wall_data["area"]
            else:
                print(f"Keine Fläche für Wand {wall.Name if wall.Name else wall.GlobalId} gefunden")
        
        # Fenster analysieren
        print("\nAnalysiere Fenster...")
        for window in windows:
            orientation = self._get_window_orientation(window)
            window_data = self._get_window_data(window)
            
            if window_data["area"]:
                analysis[orientation]["windows"].append(window_data)
                analysis[orientation]["window_area"] += window_data["area"]
            else:
                print(f"Keine Maße für Fenster {window.Name if window.Name else window.GlobalId} gefunden")
        
        self._print_analysis(analysis)
        return analysis

    def _get_wall_orientation(self, wall) -> str:
        """Ermittelt die Orientierung einer Wand"""
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                if rel.RelatingPropertyDefinition.Name == "Pset_AnalysisProperties":
                    for prop in rel.RelatingPropertyDefinition.HasProperties:
                        if prop.Name == "Orientation":
                            return prop.NominalValue.wrappedValue
        return "Unbestimmt"

    def _get_window_orientation(self, window) -> str:
        """Ermittelt die Orientierung eines Fensters über die Host-Wand"""
        for rel in self.ifc_file.get_inverse(window):
            if rel.is_a('IfcRelFillsElement'):
                opening = rel.RelatingOpeningElement
                for void_rel in self.ifc_file.get_inverse(opening):
                    if void_rel.is_a('IfcRelVoidsElement'):
                        host_wall = void_rel.RelatingBuildingElement
                        return self._get_wall_orientation(host_wall)
        return "Unbestimmt"

    def _get_window_data(self, window) -> Dict:
        """Sammelt alle relevanten Daten eines Fensters aus Qto_WindowBaseQuantities"""
        data = {
            "id": window.GlobalId,
            "name": window.Name,
            "height": 0,
            "width": 0,
            "area": 0
        }
        
        # Suche in Qto_WindowBaseQuantities
        for rel in window.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                qto = rel.RelatingPropertyDefinition
                if qto.is_a("IfcElementQuantity") and qto.Name == "Qto_WindowBaseQuantities":
                    for q in qto.Quantities:
                        if q.Name == "Height":
                            data["height"] = float(q.LengthValue)
                        elif q.Name == "Width":
                            data["width"] = float(q.LengthValue)
                        elif q.Name == "Area":
                            data["area"] = float(q.AreaValue)
        
        # Wenn keine Area gefunden wurde, aber Höhe und Breite vorhanden sind
        if not data["area"] and data["height"] and data["width"]:
            data["area"] = data["height"] * data["width"]
        
        return data

    def _get_wall_data(self, wall) -> Dict:
        """Sammelt alle relevanten Daten einer Wand aus Qto_WallBaseQuantities"""
        data = {
            "id": wall.GlobalId,
            "name": wall.Name,
            "height": 0,
            "length": 0,
            "area": 0,
            "net_area": 0  # Fläche abzüglich Öffnungen
        }
        
        # Suche in Qto_WallBaseQuantities
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                qto = rel.RelatingPropertyDefinition
                if qto.is_a("IfcElementQuantity") and qto.Name == "Qto_WallBaseQuantities":
                    for q in qto.Quantities:
                        if q.Name == "Height":
                            data["height"] = float(q.LengthValue)
                        elif q.Name == "Length":
                            data["length"] = float(q.LengthValue)
                        elif q.Name == "GrossArea":
                            data["area"] = float(q.AreaValue)
                        elif q.Name == "NetArea":
                            data["net_area"] = float(q.AreaValue)
        
        return data

    def _print_analysis(self, analysis: Dict):
        """Gibt die Analyseergebnisse aus"""
        print("\nAnalyseergebnisse nach Orientierung:")
        print("===================================")
        
        total_wall_area = 0
        total_window_area = 0
        
        for orientation, data in analysis.items():
            if data["walls"] or data["windows"]:
                print(f"\n{orientation}:")
                print(f"  Wände: {len(data['walls'])}")
                print(f"  Wandfläche (brutto): {round(data['wall_area'], 2)} m²")
                
                net_wall_area = sum(wall["net_area"] for wall in data["walls"] if wall["net_area"])
                if net_wall_area:
                    print(f"  Wandfläche (netto): {round(net_wall_area, 2)} m²")
                
                print(f"  Fenster: {len(data['windows'])}")
                print(f"  Fensterfläche: {round(data['window_area'], 2)} m²")
                
                if data["wall_area"] > 0:
                    window_wall_ratio = (data['window_area'] / data['wall_area']) * 100
                    print(f"  Fensterflächenanteil: {round(window_wall_ratio, 1)}%")
                
                total_wall_area += data["wall_area"]
                total_window_area += data["window_area"]
                
                if data["windows"]:
                    print("  Fensterdetails:")
                    for window in data["windows"]:
                        print(f"    - {window['name'] if window['name'] else window['id']}:")
                        print(f"      Höhe: {window['height']} m")
                        print(f"      Breite: {window['width']} m")
                        print(f"      Fläche: {round(window['area'], 2)} m²")

        print("\nGesamtstatistik:")
        print("===============")
        print(f"Gesamtwandfläche: {round(total_wall_area, 2)} m²")
        print(f"Gesamtfensterfläche: {round(total_window_area, 2)} m²")
        if total_wall_area > 0:
            total_ratio = (total_window_area / total_wall_area) * 100
            print(f"Gesamter Fensterflächenanteil: {round(total_ratio, 1)}%")

if __name__ == "__main__":
    analyzer = IFCBuildingAnalyzer("data/ifc/Model.ifc")
    analyzer.analyze_building() 
import ifcopenshell
import numpy as np
import math

def calculate_orientation(direction_vector, north_angle=0):
    """
    Berechnet die Himmelsrichtung basierend auf einem Richtungsvektor und dem Nordwinkel
    north_angle: Winkel in Grad, 0 = Y-Achse ist Norden
    """
    # Normalisierung des Vektors
    if len(direction_vector) == 2:
        x, y = direction_vector
    else:
        x, y = direction_vector[0], direction_vector[1]
    
    # Winkel zur Y-Achse berechnen (im Uhrzeigersinn)
    angle = math.degrees(math.atan2(x, y))
    
    # Korrektur um den Nordwinkel
    adjusted_angle = (angle - north_angle) % 360

    # Himmelsrichtung bestimmen
    if 315 <= adjusted_angle or adjusted_angle < 45:
        return "Nord"
    elif 45 <= adjusted_angle < 135:
        return "Ost"
    elif 135 <= adjusted_angle < 225:
        return "Süd"
    else:
        return "West"

def analyze_building_orientations(ifc_file, north_angle=0):
    """
    Analysiert die Orientierung aller Wände und Fenster
    """
    walls = ifc_file.by_type("IfcWall")
    windows = ifc_file.by_type("IfcWindow")
    
    wall_orientations = {"Nord": [], "Ost": [], "Süd": [], "West": [], "Unbestimmt": []}
    window_orientations = {"Nord": [], "Ost": [], "Süd": [], "West": [], "Unbestimmt": []}
    
    # Dictionary für Wand-Orientierungen erstellen
    wall_orientation_dict = {}
    
    # Wände analysieren und speichern
    for wall in walls:
        orientation = "Unbestimmt"
        try:
            if wall.ObjectPlacement and wall.ObjectPlacement.RelativePlacement:
                placement = wall.ObjectPlacement.RelativePlacement
                if hasattr(placement, 'RefDirection') and placement.RefDirection:
                    direction = placement.RefDirection.DirectionRatios
                    orientation = calculate_orientation(direction, north_angle)
                elif hasattr(placement, 'Axis') and placement.Axis:
                    direction = placement.Axis.DirectionRatios
                    orientation = calculate_orientation(direction, north_angle)
        except:
            pass
            
        wall_orientations[orientation].append(wall)
        wall_orientation_dict[wall.GlobalId] = orientation

    # Fenster analysieren
    for window in windows:
        orientation = "Unbestimmt"
        host_wall = None

        # Suche nach der Host-Wand über FillsVoids/VoidsElements Beziehung
        for rel in ifc_file.get_inverse(window):
            if rel.is_a('IfcRelFillsElement'):
                opening = rel.RelatingOpeningElement
                for void_rel in ifc_file.get_inverse(opening):
                    if void_rel.is_a('IfcRelVoidsElement'):
                        host_wall = void_rel.RelatingBuildingElement
                        break
                break

        # Wenn Host-Wand gefunden wurde, nutze deren Orientierung
        if host_wall and host_wall.GlobalId in wall_orientation_dict:
            orientation = wall_orientation_dict[host_wall.GlobalId]
            print(f"Debug - Fenster {window.Name}: Gefunden in Wand {host_wall.Name} mit Orientierung {orientation}")
        else:
            print(f"Debug - Fenster {window.Name}: Keine Host-Wand gefunden")
            
        window_orientations[orientation].append(window)

    # Ergebnisse ausgeben
    print("\nWandanalyse nach Himmelsrichtung:")
    print("================================")
    for orientation, walls_list in wall_orientations.items():
        print(f"\n{orientation}:")
        print(f"  Anzahl Wände: {len(walls_list)}")
        for wall in walls_list:
            print(f"    - {wall.Name if wall.Name else wall.GlobalId}")
    
    print("\nFensteranalyse nach Himmelsrichtung:")
    print("==================================")
    for orientation, windows_list in window_orientations.items():
        total_area = 0
        print(f"\n{orientation}:")
        print(f"  Anzahl Fenster: {len(windows_list)}")
        
        for window in windows_list:
            # Dimensionen aus EPset_Opening holen
            width = None
            height = None
            
            # Versuche zuerst die Werte direkt aus dem Fenster zu holen
            for rel in window.IsDefinedBy:
                if rel.is_a("IfcRelDefinesByProperties"):
                    props = rel.RelatingPropertyDefinition
                    if props.is_a("IfcPropertySet") and props.Name == "EPset_Opening":
                        for prop in props.HasProperties:
                            if prop.Name == "OverallHeight":
                                height = prop.NominalValue.wrappedValue
                            elif prop.Name == "OverallWidth":
                                width = prop.NominalValue.wrappedValue

            # Wenn keine Werte gefunden wurden, versuche es über den WindowType
            if not width or not height:
                if window.IsTypedBy:
                    window_type = window.IsTypedBy[0].RelatingType
                    for rel in window_type.HasPropertySets:
                        if rel.Name == "EPset_Opening":
                            for prop in rel.HasProperties:
                                if prop.Name == "OverallHeight":
                                    height = prop.NominalValue.wrappedValue
                                elif prop.Name == "OverallWidth":
                                    width = prop.NominalValue.wrappedValue
            
            if width and height:
                area = width * height
                total_area += area
                print(f"    - {window.Name if window.Name else window.GlobalId}: {round(area, 2)} m²")
            else:
                print(f"    - {window.Name if window.Name else window.GlobalId}: Keine Maße verfügbar")
        
        print(f"  Gesamtfläche: {round(total_area, 2)} m²")

    return wall_orientations, window_orientations

def write_orientations_to_elements(ifc_file, north_angle=0):
    """
    Ermittelt die Orientierungen und schreibt sie als Property auf die Elemente
    """
    walls = ifc_file.by_type("IfcWall")
    windows = ifc_file.by_type("IfcWindow")
    
    # Dictionary für Wand-Orientierungen
    wall_orientation_dict = {}
    
    # Wände analysieren und Properties schreiben
    for wall in walls:
        orientation = "Unbestimmt"
        try:
            if wall.ObjectPlacement and wall.ObjectPlacement.RelativePlacement:
                placement = wall.ObjectPlacement.RelativePlacement
                if hasattr(placement, 'RefDirection') and placement.RefDirection:
                    direction = placement.RefDirection.DirectionRatios
                    orientation = calculate_orientation(direction, north_angle)
                elif hasattr(placement, 'Axis') and placement.Axis:
                    direction = placement.Axis.DirectionRatios
                    orientation = calculate_orientation(direction, north_angle)
        except:
            pass
            
        wall_orientation_dict[wall.GlobalId] = orientation
        
        # Property Set für Orientierung erstellen/aktualisieren
        pset_name = "Pset_AnalysisProperties"
        property_name = "Orientation"
        
        # Existierendes Property Set suchen oder neues erstellen
        pset = None
        for rel in wall.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                if rel.RelatingPropertyDefinition.Name == pset_name:
                    pset = rel.RelatingPropertyDefinition
                    break
        
        if not pset:
            pset = ifc_file.createIfcPropertySet(
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=wall.OwnerHistory,
                Name=pset_name,
                Description="Analyseeigenschaften",
                HasProperties=[]
            )
            # Verknüpfung mit der Wand erstellen
            ifc_file.createIfcRelDefinesByProperties(
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=wall.OwnerHistory,
                RelatedObjects=[wall],
                RelatingPropertyDefinition=pset
            )
        
        # Property erstellen oder aktualisieren
        orientation_prop = None
        for prop in pset.HasProperties:
            if prop.Name == property_name:
                orientation_prop = prop
                break
        
        if orientation_prop:
            orientation_prop.NominalValue = ifc_file.createIfcLabel(orientation)
        else:
            orientation_prop = ifc_file.createIfcPropertySingleValue(
                Name=property_name,
                Description="Himmelsrichtung des Elements",
                NominalValue=ifc_file.createIfcLabel(orientation),
                Unit=None
            )
            pset.HasProperties = list(pset.HasProperties) + [orientation_prop]

    # Fenster analysieren und Properties schreiben
    for window in windows:
        orientation = "Unbestimmt"
        host_wall = None

        # Host-Wand finden
        for rel in ifc_file.get_inverse(window):
            if rel.is_a('IfcRelFillsElement'):
                opening = rel.RelatingOpeningElement
                for void_rel in ifc_file.get_inverse(opening):
                    if void_rel.is_a('IfcRelVoidsElement'):
                        host_wall = void_rel.RelatingBuildingElement
                        break
                break

        if host_wall and host_wall.GlobalId in wall_orientation_dict:
            orientation = wall_orientation_dict[host_wall.GlobalId]
        
        # Property Set für Fenster erstellen/aktualisieren
        pset_name = "Pset_AnalysisProperties"
        property_name = "Orientation"
        
        pset = None
        for rel in window.IsDefinedBy:
            if rel.is_a("IfcRelDefinesByProperties"):
                if rel.RelatingPropertyDefinition.Name == pset_name:
                    pset = rel.RelatingPropertyDefinition
                    break
        
        if not pset:
            pset = ifc_file.createIfcPropertySet(
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=window.OwnerHistory,
                Name=pset_name,
                Description="Analyseeigenschaften",
                HasProperties=[]
            )
            ifc_file.createIfcRelDefinesByProperties(
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=window.OwnerHistory,
                RelatedObjects=[window],
                RelatingPropertyDefinition=pset
            )
        
        # Property erstellen oder aktualisieren
        orientation_prop = None
        for prop in pset.HasProperties:
            if prop.Name == property_name:
                orientation_prop = prop
                break
        
        if orientation_prop:
            orientation_prop.NominalValue = ifc_file.createIfcLabel(orientation)
        else:
            orientation_prop = ifc_file.createIfcPropertySingleValue(
                Name=property_name,
                Description="Himmelsrichtung des Elements",
                NominalValue=ifc_file.createIfcLabel(orientation),
                Unit=None
            )
            pset.HasProperties = list(pset.HasProperties) + [orientation_prop]

    return "Orientierungen wurden erfolgreich auf alle Wände und Fenster geschrieben."

# Verwendung:
if __name__ == "__main__":
    ifc_file = ifcopenshell.open("data/ifc/Model.ifc")
    result = write_orientations_to_elements(ifc_file, north_angle=0)
    print(result)
    ifc_file.write("data/ifc/Model.ifc")
import ifcopenshell
import ifcopenshell.geom 
import numpy as np
import random
import time

ifc_file = ifcopenshell.open("data/ifc/Model.ifc")

buildings = ifc_file.by_type("IfcBuilding")

for building in buildings:
    print(f"Gebäude: {building.Name}, GUID: {building.GlobalId}")

storeys = ifc_file.by_type("IfcBuildingStorey")

for storey in storeys:
    print(f"Stockwerk: {storey.Name}, Höhe: {storey.Elevation}")

spaces = ifc_file.by_type("IfcSpace")

for space in spaces:
    for rel in space.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            props = rel.RelatingPropertyDefinition
            if props.is_a("IfcPropertySet"):
                for p in props.HasProperties:
                    if p.Name == "NetVolume":
                        print(f"Raum: {space.Name}, Volumen: {p.NominalValue.wrappedValue} m³")

# Wände abrufen und mit zufälligen U-Werten versehen
walls = ifc_file.by_type("IfcWall")

# Fenster nach Himmelsrichtung analysieren
windows = ifc_file.by_type("IfcWindow")
window_types = ifc_file.by_type("IfcWindowType")
print("\nFensterflächenanalyse:")
print("=====================")

for window in windows:
    width = None
    height = None
    orientation = "Unbestimmt"
    
    # Werte direkt aus dem Fenster oder seinem Typ auslesen
    for rel in window.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            props = rel.RelatingPropertyDefinition
            if props.is_a("IfcPropertySet"):
                if props.Name == "EPset_Opening":
                    for prop in props.HasProperties:
                        if prop.Name == "OverallHeight":
                            height = prop.NominalValue.wrappedValue
                        elif prop.Name == "OverallWidth":
                            width = prop.NominalValue.wrappedValue
                elif props.Name == "Pset_WindowCommon":
                    for prop in props.HasProperties:
                        if prop.Name == "Orientation":
                            orientation = prop.NominalValue.wrappedValue

    # Falls keine Werte gefunden wurden, im WindowType nachschauen
    if not width or not height:
        window_type = window.IsTypedBy[0].RelatingType if window.IsTypedBy else None
        if window_type:
            for rel in window_type.HasPropertySets:
                if rel.Name == "EPset_Opening":
                    for prop in rel.HasProperties:
                        if prop.Name == "OverallHeight":
                            height = prop.NominalValue.wrappedValue
                        elif prop.Name == "OverallWidth":
                            width = prop.NominalValue.wrappedValue

    # Wenn immer noch keine Werte gefunden wurden, direkte Attribute prüfen
    if not width:
        width = getattr(window, 'OverallWidth', None)
    if not height:
        height = getattr(window, 'OverallHeight', None)

    if width and height:
        area = round(width * height, 2)
        print(f"Fenster {window.GlobalId}:")
        print(f"  Name: {window.Name if window.Name else 'Unbenannt'}")
        print(f"  Orientierung: {orientation}")
        print(f"  Breite: {width} m")
        print(f"  Höhe: {height} m")
        print(f"  Fläche: {area} m²")
        print("  ---")

# Gesamtstatistik
total_window_area = 0
window_count = 0
windows_with_dimensions = 0

for window in windows:
    width = None
    height = None
    
    # Gleiche Logik wie oben für die Dimensionssuche...
    for rel in window.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            props = rel.RelatingPropertyDefinition
            if props.is_a("IfcPropertySet") and props.Name == "EPset_Opening":
                width = next((prop.NominalValue.wrappedValue for prop in props.HasProperties if prop.Name == "OverallWidth"), None)
                height = next((prop.NominalValue.wrappedValue for prop in props.HasProperties if prop.Name == "OverallHeight"), None)
    
    if not width or not height:
        window_type = window.IsTypedBy[0].RelatingType if window.IsTypedBy else None
        if window_type:
            for rel in window_type.HasPropertySets:
                if rel.Name == "EPset_Opening":
                    width = next((prop.NominalValue.wrappedValue for prop in rel.HasProperties if prop.Name == "OverallWidth"), None)
                    height = next((prop.NominalValue.wrappedValue for prop in rel.HasProperties if prop.Name == "OverallHeight"), None)

    if width and height:
        total_window_area += width * height
        windows_with_dimensions += 1
    window_count += 1

print("\nGesamtstatistik:")
print(f"Gesamtanzahl Fenster: {window_count}")
print(f"Fenster mit Maßangaben: {windows_with_dimensions}")
print(f"Gesamtfensterfläche: {round(total_window_area, 2)} m²")
print(f"Durchschnittliche Fensterfläche: {round(total_window_area/windows_with_dimensions if windows_with_dimensions > 0 else 0, 2)} m²")

windows = ifc_file.by_type("IfcWindow")
print("\nProperty Set Diagnose:")
print("=====================")

# Erstes Fenster als Beispiel nehmen
if windows:
    window = windows[0]
    print(f"Gefundene Fenster: {len(windows)}")
    print("\nVerfügbare Property Sets für erstes Fenster:")
    
    for rel in window.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            props = rel.RelatingPropertyDefinition
            if props.is_a("IfcPropertySet"):
                print(f"\nProperty Set Name: {props.Name}")
                print("Properties:")
                for prop in props.HasProperties:
                    print(f"  - {prop.Name}: {prop.NominalValue.wrappedValue if hasattr(prop, 'NominalValue') else 'N/A'}")
else:
    print("Keine Fenster in der IFC-Datei gefunden!")

def create_owner_history(ifc_file):
    """Erstellt einen IfcOwnerHistory Eintrag falls nicht vorhanden"""
    # Prüfe ob bereits OwnerHistory existiert
    owner_history = ifc_file.by_type("IfcOwnerHistory")
    if owner_history:
        return owner_history[0]
    
    # Erstelle notwendige Einträge
    person = ifc_file.createIfcPerson(
        GivenName="Admin",
        FamilyName="User"
    )
    
    organization = ifc_file.createIfcOrganization(
        Name="Organization"
    )
    
    person_and_org = ifc_file.createIfcPersonAndOrganization(
        ThePerson=person,
        TheOrganization=organization
    )
    
    application = ifc_file.createIfcApplication(
        ApplicationDeveloper=organization,
        Version="1.0",
        ApplicationFullName="IFC Property Manager",
        ApplicationIdentifier="IFC_PM"
    )
    
    return ifc_file.createIfcOwnerHistory(
        OwningUser=person_and_org,
        OwningApplication=application,
        State="READWRITE",
        ChangeAction="ADDED",
        CreationDate=int(time.time())
    )

def create_pset(ifc_file, pset_name: str, properties: list) -> object:
    """Erstellt ein neues PropertySet"""
    # Stelle sicher dass OwnerHistory existiert
    owner_history = create_owner_history(ifc_file)
    
    pset = ifc_file.createIfcPropertySet(
        ifcopenshell.guid.new(),
        owner_history,
        pset_name,
        None,
        [ifc_file.createIfcPropertySingleValue(name, None, ifc_file.create_entity(value_type, value), None)
         for name, value_type, value in properties]
    )
    return pset

def assign_pset(element, pset):
    """Weist einem Element ein PropertySet zu"""
    # Erstelle neue Relation wenn IsDefinedBy nicht existiert
    if not hasattr(element, "IsDefinedBy"):
        # Erstelle neue Relation
        rel = element.file.createIfcRelDefinesByProperties(
            ifcopenshell.guid.new(),
            create_owner_history(element.file),
            None,
            None,
            [element],
            pset
        )
        return

    # Wenn IsDefinedBy existiert, prüfe auf existierendes PropertySet
    for rel in element.IsDefinedBy:
        if rel.is_a("IfcRelDefinesByProperties"):
            if rel.RelatingPropertyDefinition.Name == pset.Name:
                # Update existierendes PropertySet
                rel.RelatingPropertyDefinition = pset
                return

    # Wenn kein passendes PropertySet gefunden wurde, füge neues hinzu
    rel = element.file.createIfcRelDefinesByProperties(
        ifcopenshell.guid.new(),
        create_owner_history(element.file),
        None,
        None,
        [element],
        pset
    )

def add_thermal_properties(ifc_file_path: str):
    """Fügt thermische Eigenschaften zu Bauteilen hinzu und speichert die Datei"""
    ifc_file = ifcopenshell.open(ifc_file_path)
    
    print("\nFüge thermische Eigenschaften zu Dächern hinzu...")
    roofs = ifc_file.by_type("IfcRoof")
    print(f"Gefundene Dächer: {len(roofs)}")
    
    for i, element in enumerate(roofs, 1):
        u_value = round(random.uniform(0.8, 1.8), 2)
        
        pset = create_pset(ifc_file, "Pset_RoofCommon", [
            ("ThermalTransmittance", "IfcThermalTransmittanceMeasure", u_value),
            ("SolarAbsorption", "IfcPositiveRatioMeasure", round(random.uniform(0.5, 0.8), 2)),
            ("Emissivity", "IfcPositiveRatioMeasure", round(random.uniform(0.8, 0.95), 2)),
            ("Reflectance", "IfcPositiveRatioMeasure", round(random.uniform(0.2, 0.5), 2))
        ])
        
        assign_pset(element, pset)
        print(f"Dach {i}/{len(roofs)} verarbeitet (U-Wert: {u_value})")
    
    # Speichern der Änderungen
    output_path = ifc_file_path
    ifc_file.write(output_path)
    print(f"\nDatei gespeichert unter: {output_path}")

if __name__ == "__main__":
    add_thermal_properties("data/ifc/Model.ifc")







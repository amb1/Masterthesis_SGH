import ifcopenshell

# IFC-Datei öffnen
ifc_file = ifcopenshell.open("E:/ambi/Code/SGH-Master-Github/local/data/ifc/Model.ifc")

# Alle IFC-Typen im Modell auflisten
element_types = set(entity.is_a() for entity in ifc_file.by_type("IfcProduct"))
print(f"📌 Enthaltene IFC-Elemente: {element_types}")
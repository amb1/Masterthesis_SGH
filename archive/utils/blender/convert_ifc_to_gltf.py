import ifcopenshell
import bpy
import ifcopenshell.geom
import mathutils

# ✅ IFC-Datei laden
ifc_path = "E:/ambi/Code/SGH-Master-Github/data/ifc/Model.ifc"
ifc_file = ifcopenshell.open(ifc_path)

# 🔄 IfcOpenShell Geometrie-Einstellungen
settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)  # Nutzt globale Koordinaten

# ✅ Szene in Blender bereinigen
bpy.ops.wm.read_factory_settings(use_empty=True)

# 🔄 Durch alle IFC-Produkte iterieren
for product in ifc_file.by_type("IfcProduct"):
    try:
        shape = ifcopenshell.geom.create_shape(settings, product)

        # 🏗 Blender-Mesh erstellen
        mesh = bpy.data.meshes.new(name=product.Name or product.GlobalId)
        obj = bpy.data.objects.new(mesh.name, mesh)
        bpy.context.collection.objects.link(obj)

        # 🏗 IFC-Vertex-Daten in Blender übernehmen
        mesh.from_pydata(shape.geometry.verts, [], shape.geometry.faces)
        mesh.update()

        # 🏗 IFC-Hierarchie einhalten (Spatial Decomposition)
        if hasattr(product, "ContainedInStructure"):
            for rel in product.ContainedInStructure:
                parent = rel.RelatingStructure
                if parent:
                    obj.parent = bpy.data.objects.get(parent.Name or parent.GlobalId)

        print(f"✅ {product.is_a()} '{product.Name}' importiert.")

    except Exception as e:
        print(f"⚠️ Fehler beim Laden von {product.is_a()} '{product.Name}': {e}")

print("✅ IFC-Import abgeschlossen!")

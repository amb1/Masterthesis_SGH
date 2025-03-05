import subprocess

# Blender-Pfad
blender_path = r"F:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

# IFC- und glTF-Dateipfade
ifc_file = r"E:\ambi\Code\SGH-Master-Github\input.ifc"
gltf_output = r"E:\ambi\Code\SGH-Master-Github\output.gltf"

# Blender-Kommando für CLI
cmd = [
    blender_path,
    # "--background",  # Hintergrund-Modus aktivieren
    "--python", r"E:\ambi\Code\SGH-Master-Github\local\utils\blender\convert_ifc_to_gltf.py",
    "--", ifc_file, gltf_output
]

# Blender-Prozess starten und UTF-8-Kodierung erzwingen
process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")

# Ausgabe in die Konsole schreiben
print(process.stdout)
print(process.stderr)

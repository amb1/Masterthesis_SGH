import sys
from pathlib import Path

# Füge Projekt-Root zum Python-Path hinzu
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import logging
import yaml
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lade Konfigurationen
config_path = project_root / 'cfg'
with open(config_path / 'data_sources' / 'vienna_citygml_normalized.yml', 'r') as f:
    citygml_config = yaml.safe_load(f)
with open(config_path / 'cea' / 'cea_fields.yml', 'r') as f:
    cea_config = yaml.safe_load(f)

# Test CityGML Extraktion
citygml_path = project_root.parent / 'local' / 'data' / 'citygml' / '099082.gml'
print(f"🔍 Suche CityGML in: {citygml_path}")

buildings_gdf = fetch_citygml_buildings(citygml_path, citygml_config, cea_config, logger)

if buildings_gdf is not None:
    print(f"✅ Gefundene Gebäude: {len(buildings_gdf)}")
    print("📊 Spalten:", buildings_gdf.columns.tolist())
    print("🌍 CRS:", buildings_gdf.crs)
    print("📐 Erste Geometrie:", buildings_gdf.geometry.iloc[0])

    # Erstelle Output-Verzeichnis
    output_dir = project_root / 'tests' / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Speichere Ergebnis
    output_file = output_dir / 'buildings.shp'
    buildings_gdf.to_file(output_file)
    print(f"💾 Ergebnis gespeichert in: {output_file}") 
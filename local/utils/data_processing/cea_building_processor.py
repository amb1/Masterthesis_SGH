import os
from pathlib import Path
import geopandas as gpd

# Füge Projekt-Root zum Python-Path hinzu wenn direkt ausgeführt
# if __name__ == "__main__":
#     project_root = Path(__file__).resolve().parent.parent.parent
#     if str(project_root) not in sys.path:
#         sys.path.append(str(project_root))
#     from utils.data_processing.base_building_processor import BaseBuildingProcessor
# else:
#     from .base_building_processor import BaseBuildingProcessor

    
class CEABuildingProcessor:
    """Basis-Klasse für CEA-spezifische Verarbeitung"""

    def __init__(self, config, cea_config):
        self.config = config
        self.cea_config = cea_config

    def setup_project_structure(self, project_name, scenario_name, project_root):
        """Erstellt die Verzeichnisstruktur für das Projekt"""
        scenario_dir = project_root / "projects" / project_name / scenario_name

        paths = {
            "scenario": scenario_dir,
            "geometry": scenario_dir / "inputs/building-geometry",
            "properties": scenario_dir / "inputs/building-properties",
            "networks": scenario_dir / "inputs/networks"
        }

        for key, path in paths.items():
            path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Verzeichnis erstellt/geprüft: {path}")

        return paths

    def save_typology_shapefile(self, typology_df, scenario_dir):
        """Speichert die Gebäudetypologie als Shapefile"""
        try:
            output_path = scenario_dir / "inputs/properties/typology.shp"
            print(f"\nSpeichere Typologie-Shapefile: {output_path}")
            
            # Erstelle ein GeoDataFrame mit einer Dummy-Geometrie (Falls keine Geometrie vorhanden)
            typology_gdf = gpd.GeoDataFrame(
                typology_df,
                geometry=gpd.points_from_xy([0] * len(typology_df), [0] * len(typology_df)),
                crs="EPSG:2056"
            )

            # Speichere als Shapefile
            typology_gdf.to_file(output_path, driver='ESRI Shapefile')
            print("✅ Typologie-Shapefile erfolgreich gespeichert")
            
        except Exception as e:
            print(f"❌ Fehler beim Speichern der Typologie: {str(e)}")

    def save_zone_shapefile(self, buildings_gdf, scenario_dir):
        """Speichert die Zone als Shapefile"""
        try:
            output_path = scenario_dir / "inputs/building-geometry/zone.shp"
            print(f"\nSpeichere Zone-Shapefile: {output_path}")

            # Stelle sicher, dass buildings_gdf ein GeoDataFrame ist
            if not isinstance(buildings_gdf, gpd.GeoDataFrame):
                raise TypeError("buildings_gdf muss ein GeoDataFrame sein")

            # Speichere als Shapefile
            buildings_gdf.to_file(output_path, driver='ESRI Shapefile')
            print("✅ Zone-Shapefile erfolgreich gespeichert")
            
        except Exception as e:
            print(f"❌ Fehler beim Speichern der Zone: {str(e)}")
            raise

    def determine_standard(self, year, building_type, renovation_status="Nicht saniert"):
        """Berechnet den Gebäudestandard"""
        try:
            # Default Suffix basierend auf Baujahr
            suffix = "_A"  # Default für alte Gebäude
            
            if year >= 2000:
                suffix = "_D"  # Neubau
            elif year >= 1980:
                suffix = "_C"  # Mittleres Alter
            elif year >= 1960:
                suffix = "_B"  # Älteres Gebäude
            
            standard = f"{building_type}{suffix}"
            
            # Füge Renovierungsstatus hinzu
            if renovation_status != "Nicht saniert":
                standard += "_NR"
                
            return standard
            
        except Exception as e:
            print(f"Fehler bei Standardbestimmung: {str(e)}")
            return "UNKNOWN"

    def create_typology(self, buildings_df):
        """Erstellt CEA-konforme Gebäudetypologie"""
        try:
            typology = buildings_df.copy()
            
            # Standardisiere Spalten
            typology['Name'] = typology['Name'].fillna('')
            typology['YEAR'] = typology['YEAR'].fillna(2000)
            typology['STANDARD'] = typology.apply(
                lambda x: self.determine_standard(x['YEAR'], x['BLDG_TYPE']), 
                axis=1
            )
            
            # Setze Default-Werte für fehlende Felder
            typology['USE1_R'] = typology['USE1_R'].fillna(1.0)
            typology['USE2'] = typology['USE2'].fillna('NONE')
            typology['USE2_R'] = typology['USE2_R'].fillna(0.0)
            
            return typology
            
        except Exception as e:
            print(f"Fehler bei Typologieerstellung: {str(e)}")
            raise

    def create_scenarios(self, buildings_df, scenario_path):
        """Erstellt die drei CEA-Szenarien"""
        try:
            # Basis-Szenario
            base_scenario = self.create_typology(buildings_df)
            self.save_as_dbf(base_scenario, scenario_path / "baseline")
            
            # 2030 Szenario
            scenario_2030 = base_scenario.copy()
            scenario_2030['STANDARD'] = scenario_2030['STANDARD'].apply(
                lambda x: x + "_R" if not x.endswith("_R") else x
            )
            self.save_as_dbf(scenario_2030, scenario_path / "2030")
            
            # 2050 Szenario
            scenario_2050 = scenario_2030.copy()
            scenario_2050['STANDARD'] = scenario_2050['STANDARD'].apply(
                lambda x: x.replace("_R", "_HR")
            )
            self.save_as_dbf(scenario_2050, scenario_path / "2050")
            
        except Exception as e:
            print(f"Fehler bei Szenarienerstellung: {str(e)}")
            raise 

    def validate_building_data(self, building_data: dict) -> bool:
        """Validiert die Gebäudedaten"""
        required_fields = ['Name', 'YEAR', 'STANDARD', 'USE1']
        
        for field in required_fields:
            if field not in building_data:
                self.logger.warning(f"Fehlendes Pflichtfeld: {field}")
                return False
            
        return True

    def validate_geometry(self, geometry) -> bool:
        """Validiert die Gebäudegeometrie"""
        if not geometry or not geometry.is_valid:
            self.logger.warning("Ungültige Geometrie")
            return False
        return True

def main():
    """Test-Ausführung"""
    try:
        print("CEA Building Processor Test")
        # Test-Code hier...
    except Exception as e:
        print(f"Fehler: {str(e)}")

if __name__ == "__main__":
    main() 
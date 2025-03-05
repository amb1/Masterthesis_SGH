import os
from pathlib import Path
import geopandas as gpd
import yaml

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

    def __init__(self, cea_config):
        """Initialisiert den CEA Building Processor.
        
        Args:
            cea_config: Die Konfiguration mit den CEA-Feldern
        """
        self.cea_config = cea_config
        self.zone_fields = cea_config.get('cea_fields', {}).get('zone', {})
        self.typology_fields = cea_config.get('cea_fields', {}).get('typology', {})
        self.file_formats = cea_config['file_formats']
        self.paths = cea_config['paths']

    def setup_project_structure(self, project_name, scenario_name, project_root):
        """Erstellt die Verzeichnisstruktur für das Projekt"""
        scenario_dir = project_root / "projects" / project_name / scenario_name

        paths = {
            "scenario": scenario_dir,
            "geometry": scenario_dir / self.paths['outputs']['geometry'],
            "properties": scenario_dir / self.paths['outputs']['properties'],
            "networks": scenario_dir / self.paths['outputs']['networks']
        }

        for key, path in paths.items():
            path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Verzeichnis erstellt/geprüft: {path}")

        return paths

    def save_zone_shapefile(self, buildings_gdf, project_paths):
        """Speichert die Zone-Shapefile"""
        output_file = project_paths['geometry'] / "zone.shp"
        
        # Explizit den Geometrietyp setzen
        if not buildings_gdf.empty:
            geom_type = buildings_gdf.geometry.iloc[0].geom_type
            buildings_gdf.to_file(
                output_file, 
                driver=self.file_formats['shp_driver'],
                geometry_type=geom_type  # Wichtig: Korrekten Geometrietyp setzen
            )
            logger.info(f"✅ Zone-Shapefile gespeichert mit Geometrietyp: {geom_type}")

    def save_typology_shapefile(self, buildings_gdf, project_paths):
        """Speichert die Typologie-Shapefile"""
        output_file = project_paths['geometry'] / "typology.shp"
        buildings_gdf.to_file(
            output_file, 
            driver=self.file_formats['shp_driver']
        )

    def determine_standard(self, year, building_type, renovation_status="Nicht saniert"):
        """Berechnet den Gebäudestandard basierend auf Bauperiode und Gebäudetyp"""
        try:
            # Lade WFS-Konfiguration
            config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "wfs" / "wfs_config.yml"
            with open(config_path, "r", encoding="utf-8") as file:
                wfs_config = yaml.safe_load(file)['vienna_wfs']

            # Bestimme Bauperiode
            period_suffix = "_A"  # Default
            if year <= 1918:
                period_suffix = "_A"  # 1848-1918
            elif year <= 1945:
                period_suffix = "_C"  # 1919-1945
            else:
                # Nach 1945: Detailliertere Kategorisierung
                if year <= 1957:
                    period_suffix = "_D"
                elif year <= 1968:
                    period_suffix = "_E"
                elif year <= 1978:
                    period_suffix = "_F"
                elif year <= 1983:
                    period_suffix = "_G"
                elif year <= 1994:
                    period_suffix = "_H"
                elif year <= 2001:
                    period_suffix = "_I"
                elif year <= 2009:
                    period_suffix = "_J"
                elif year <= 2015:
                    period_suffix = "_K"
                else:
                    period_suffix = "_L"

            # Kombiniere Gebäudetyp und Bauperiode
            standard = f"{building_type}{period_suffix}"
            
            # Füge Renovierungsstatus hinzu
            if renovation_status != "Nicht saniert":
                standard += "_NR"
                
            return standard
            
        except Exception as e:
            logger.error(f"Fehler bei Standardbestimmung: {str(e)}")
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

    def process_building(self, building):
        """
        Verarbeitet ein einzelnes Gebäude und gibt die verarbeiteten Daten zurück.
        
        Args:
            building: Ein Dictionary mit den Gebäudedaten
            
        Returns:
            Ein Dictionary mit den verarbeiteten Daten für zone.shp und typology.shp
        """
        if not isinstance(building, dict):
            # Wenn building kein Dictionary ist, konvertiere es in eins
            building = {
                'building_id': str(building),
                'height_ag': 0,
                'floors_ag': 0,
                'roof_type': 'UNKNOWN'
            }
            
        processed = {}
        
        # Verarbeite die Felder für zone.shp
        for field, field_config in self.zone_fields.items():
            field_type = field_config.get('type', 'str')
            default_value = field_config.get('default', '')
            
            # Hole den Wert aus dem building Dictionary
            value = building.get(field, default_value)
            
            # Konvertiere den Wert in den richtigen Typ
            try:
                if field_type == 'int':
                    processed[field] = int(float(value)) if value != '' else 0
                elif field_type == 'float':
                    processed[field] = float(value) if value != '' else 0.0
                else:
                    processed[field] = str(value)
            except (ValueError, TypeError):
                processed[field] = default_value
                
        # Verarbeite die Felder für typology.shp
        for field, field_config in self.typology_fields.items():
            field_type = field_config.get('type', 'str')
            default_value = field_config.get('default', '')
            
            # Hole den Wert aus dem building Dictionary
            value = building.get(field, default_value)
            
            # Konvertiere den Wert in den richtigen Typ
            try:
                if field_type == 'int':
                    processed[field] = int(float(value)) if value != '' else 0
                elif field_type == 'float':
                    processed[field] = float(value) if value != '' else 0.0
                else:
                    processed[field] = str(value)
            except (ValueError, TypeError):
                processed[field] = default_value
                
        return processed

def main():
    """Test-Ausführung"""
    try:
        print("CEA Building Processor Test")
        # Test-Code hier...
    except Exception as e:
        print(f"Fehler: {str(e)}")

if __name__ == "__main__":
    main() 
from pathlib import Path

class ProjectPaths:
    def __init__(self, project_name: str, scenario_name: str):
        self.project_name = project_name
        self.scenario_name = scenario_name
        self.base_path = self._setup_paths()
        
    def _setup_paths(self) -> dict:
        """Erstellt die Projektstruktur basierend auf Projekt- und Szenarionamen"""
        base_path = Path(self.project_name) / self.scenario_name / "inputs"
        
        paths = {
            "geometry": base_path / "building-geometry",
            "properties": base_path / "building-properties",
            "networks": base_path / "building-networks"
        }
        
        # Erstelle Verzeichnisse
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
            
        return paths
    
    def get_path(self, path_type: str) -> Path:
        """Gibt den Pfad für den angegebenen Typ zurück"""
        return self.base_path[path_type]

def setup_project_paths():
    """Interaktive Eingabe der Projekt- und Szenarionamen"""
    print("\nProjekt-Setup")
    print("=" * 50)
    
    project_name = input("Bitte Projektnamen eingeben: ")
    scenario_name = input("Bitte Szenarionamen eingeben: ")
    
    paths = ProjectPaths(project_name, scenario_name)
    
    print("\nErstellte Verzeichnisse:")
    for path_type, path in paths.base_path.items():
        print(f"- {path_type}: {path}")
        
    return paths 
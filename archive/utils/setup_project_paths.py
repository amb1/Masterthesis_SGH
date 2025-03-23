from pathlib import Path
import logging

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProjectPaths:
    def __init__(self, project_name: str, scenario_name: str):
        """Initialisiert die Projektstruktur.
        
        Args:
            project_name (str): Name des Projekts
            scenario_name (str): Name des Szenarios
        """
        self.project_name = project_name
        self.scenario_name = scenario_name
        self.base_path = self._setup_paths()
        
    def _setup_paths(self) -> dict:
        """Erstellt die CEA-Projektstruktur basierend auf Projekt- und Szenarionamen"""
        # Erstelle absolute Pfade
        local_dir = Path(__file__).resolve().parent.parent
        base_path = local_dir / "projects" / self.project_name / self.scenario_name
        
        # Definiere die CEA-Struktur
        paths = {
            'inputs': {
                'building-geometry': base_path / 'inputs' / 'building-geometry',
                'building-properties': base_path / 'inputs' / 'building-properties',
                'networks': base_path / 'inputs' / 'networks'
            }
        }
        
        # Erstelle Verzeichnisse
        for category in paths['inputs'].values():
            category.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Verzeichnis erstellt: {category}")
            
        return paths
    
    def get_path(self, category: str) -> Path:
        """Gibt den Pfad für die angegebene Kategorie zurück.
        
        Args:
            category (str): Kategorie (building-geometry, building-properties, networks)
            
        Returns:
            Path: Pfad zum Verzeichnis
        """
        return self.base_path['inputs'][category]

def setup_project_paths():
    """Erstellt die CEA-Projektstruktur und gibt die Pfade zurück"""
    print("\nCEA Projekt-Setup")
    print("=" * 50)
    
    # Hole Projekt- und Szenarionamen
    project_name = input("Bitte Projektnamen eingeben: ").strip()
    scenario_name = input("Bitte Szenarionamen eingeben: ").strip()
    
    # Erstelle Projektstruktur
    paths = ProjectPaths(project_name, scenario_name)
    
    # Zeige erstellte Struktur
    print("\nErstellte CEA-Verzeichnisstruktur:")
    for category, path in paths.base_path['inputs'].items():
        print(f"- {category}: {path}")
    
    return paths 
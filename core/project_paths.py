"""
Modul zur Verwaltung der CEA-Projektstruktur.

Dieses Modul stellt die ProjectPaths-Klasse bereit, die für die Erstellung und Verwaltung
der CEA-Projektverzeichnisstruktur verantwortlich ist.
"""

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
        root_dir = Path(__file__).resolve().parent.parent
        project_dir = root_dir / "data"
        cea_dir = root_dir / "projects" / self.project_name / self.scenario_name
        
        # Definiere die Datenstruktur
        paths = {
            'data': {
                'raw': project_dir / 'raw',
                'processed': project_dir / 'processed',
                'results': project_dir / 'results'
            },
            'cea': {
                'inputs': {
                    'building-geometry': cea_dir / 'inputs' / 'building-geometry',
                    'building-properties': cea_dir / 'inputs' / 'building-properties',
                    'networks': cea_dir / 'inputs' / 'networks'
                }
            }
        }
        
        # Erstelle Verzeichnisse
        for category in paths['data'].values():
            category.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Datenverzeichnis erstellt: {category}")
            
        for category in paths['cea']['inputs'].values():
            category.mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ CEA-Verzeichnis erstellt: {category}")
            
        return paths
    
    def get_data_path(self, category: str) -> Path:
        """Gibt den Pfad für die angegebene Datenkategorie zurück.
        
        Args:
            category (str): Kategorie (raw, processed, results)
            
        Returns:
            Path: Pfad zum Datenverzeichnis
        """
        if category not in self.base_path['data']:
            raise ValueError(f"Ungültige Datenkategorie: {category}")
        return self.base_path['data'][category]
    
    def get_cea_path(self, category: str) -> Path:
        """Gibt den Pfad für die angegebene CEA-Kategorie zurück.
        
        Args:
            category (str): Kategorie (building-geometry, building-properties, networks)
            
        Returns:
            Path: Pfad zum CEA-Verzeichnis
        """
        if category not in self.base_path['cea']['inputs']:
            raise ValueError(f"Ungültige CEA-Kategorie: {category}")
        return self.base_path['cea']['inputs'][category]

def setup_project_paths(project_name: str, scenario_name: str) -> ProjectPaths:
    """Erstellt eine neue Projektstruktur.
    
    Args:
        project_name (str): Name des Projekts
        scenario_name (str): Name des Szenarios
        
    Returns:
        ProjectPaths: Instanz der ProjectPaths-Klasse
    """
    return ProjectPaths(project_name, scenario_name)

def get_output_path(category: str = None) -> Path:
    """Gibt den Pfad zum Ausgabeverzeichnis zurück.
    
    Args:
        category (str, optional): Unterkategorie im Ausgabeverzeichnis
        
    Returns:
        Path: Pfad zum Ausgabeverzeichnis
    """
    root_dir = Path(__file__).resolve().parent.parent
    output_dir = root_dir / "outputs"
    
    if category:
        output_dir = output_dir / category
        
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_config_path(filename: str = "global.yml") -> Path:
    """Gibt den Pfad zur Konfigurationsdatei zurück.
    
    Args:
        filename (str, optional): Name der Konfigurationsdatei
        
    Returns:
        Path: Pfad zur Konfigurationsdatei
    """
    root_dir = Path(__file__).resolve().parent.parent
    config_dir = root_dir / "config"
    return config_dir / filename 
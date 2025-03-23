"""
Projektmanagement-Funktionen für CEA-Projekte.

Migrated from local/utils/project_manager.py

Dieses Modul enthält Funktionen zur Verwaltung von CEA-Projekten,
einschließlich Projektstruktur, Backup und Validierung.
"""

import logging
import sys
import shutil
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from core.logging_config import setup_logging, LoggedOperation

# Logger konfigurieren
logger = logging.getLogger(__name__)

class ProjectManager:
    """Verwaltet die Projektstruktur und -organisation."""
    
    def __init__(self, project_name: str, scenario_name: str):
        """Initialisiert den Project Manager.
        
        Args:
            project_name: Name des Projekts
            scenario_name: Name des Szenarios
        """
        self.project_name = project_name
        self.scenario_name = scenario_name
        self.project_path = Path("projects") / project_name
        self.scenario_path = self.project_path / scenario_name
        
    def create_backup(self) -> bool:
        """Erstellt ein Backup des Szenarios.
        
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        backup_path = create_backup(self.scenario_path)
        return backup_path is not None
        
    def cleanup_project(self) -> bool:
        """Bereinigt das Projektverzeichnis.
        
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        return cleanup_project(self.project_path)
        
    def validate_project_structure(self) -> bool:
        """Überprüft die CEA-Projektstruktur.
        
        Returns:
            bool: True wenn gültig, False sonst
        """
        return validate_project_structure(self.project_path, self.scenario_path)
        
    def setup_project_structure(self, base_path: Path) -> bool:
        """Erstellt die CEA-Projektstruktur.
        
        Args:
            base_path: Basis-Verzeichnis für das Projekt
            
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Erstelle Projekt- und Szenarioverzeichnisse
            self.project_path = base_path / self.project_name
            self.scenario_path = self.project_path / self.scenario_name
            
            # Erstelle Verzeichnisstruktur
            created_dirs = setup_project_structure(self.project_path, self.scenario_path)
            return bool(created_dirs)
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Erstellen der Projektstruktur: {str(e)}")
            return False

def get_project_info(args=None, test_mode=False) -> Tuple[str, str, Path, Path]:
    """
    Holt Projekt- und Szenarioinformationen entweder aus Argumenten oder interaktiv
    
    Args:
        args: Argparse Namespace mit project_name und scenario_name (optional)
        test_mode: Wenn True, werden Standardwerte für Tests verwendet
        
    Returns:
        Tuple[str, str, Path, Path]: (project_name, scenario_name, project_path, scenario_path)
        
    Raises:
        ValueError: Wenn Projekt- oder Szenarioname fehlt
    """
    if test_mode:
        project_name = "test_project"
        scenario_name = "test_scenario"
    elif args and args.project_name and args.scenario_name:
        project_name = args.project_name
        scenario_name = args.scenario_name
    else:
        print("\nCEA Projekt-Setup")
        print("=" * 50)
        project_name = input("Bitte Projektnamen eingeben: ").strip()
        
        # Zeige existierende Szenarien für das Projekt
        project_path = Path("projects") / project_name
        if project_path.exists():
            existing_scenarios = [d.name for d in project_path.iterdir() if d.is_dir()]
            if existing_scenarios:
                print(f"\nExistierende Szenarien für {project_name}:")
                for scenario in existing_scenarios:
                    print(f"- {scenario}")
                print("\n")
        
        scenario_name = input("Bitte Szenarionamen eingeben: ").strip()
    
    # Validiere Eingaben
    if not project_name or not scenario_name:
        raise ValueError("Projekt- und Szenarioname müssen angegeben werden!")
    
    # Erstelle Pfade
    project_path = Path("projects") / project_name
    scenario_path = project_path / scenario_name
    
    # Überprüfe ob Szenario bereits existiert
    if scenario_path.exists():
        if args and args.force:
            choice = 'y'
        elif test_mode:
            choice = 'y'
        else:
            print(f"\n⚠️ Szenario '{scenario_name}' existiert bereits.")
            choice = input("Möchten Sie das bestehende Szenario überschreiben? (y/n): ").lower()
        
        if choice != 'y':
            print("Abbruch.")
            sys.exit(0)
    
    return project_name, scenario_name, project_path, scenario_path

def create_backup(scenario_path: Path) -> Optional[Path]:
    """Erstellt ein Backup des Szenarios
    
    Args:
        scenario_path: Pfad zum Szenarioverzeichnis
        
    Returns:
        Optional[Path]: Pfad zum Backup-Verzeichnis oder None
    """
    try:
        with LoggedOperation("Backup erstellen"):
            # Erstelle Backup-Verzeichnis
            backup_dir = scenario_path.parent / f"{scenario_path.name}_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Kopiere Dateien
            for file_path in scenario_path.rglob('*'):
                if file_path.is_file():
                    relative_path = file_path.relative_to(scenario_path)
                    backup_path = backup_dir / relative_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    backup_path.write_bytes(file_path.read_bytes())
                    
            logger.info(f"✅ Backup erstellt: {backup_dir}")
            return backup_dir
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen des Backups: {str(e)}")
        return None

def cleanup_project(project_path: Path) -> bool:
    """Bereinigt das Projektverzeichnis
    
    Args:
        project_path: Pfad zum Projektverzeichnis
        
    Returns:
        bool: True wenn erfolgreich, False sonst
    """
    try:
        with LoggedOperation("Projekt bereinigen"):
            # Lösche temporäre Dateien
            temp_files = list(project_path.rglob('*.tmp'))
            for temp_file in temp_files:
                temp_file.unlink()
                
            # Lösche leere Verzeichnisse
            for dir_path in project_path.rglob('*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    
            logger.info("✅ Projektverzeichnis bereinigt")
            return True
            
    except Exception as e:
        logger.error(f"❌ Fehler bei der Projektbereinigung: {str(e)}")
        return False

def validate_project_structure(project_path: Path, scenario_path: Path) -> bool:
    """Überprüft die CEA-Projektstruktur
    
    Args:
        project_path: Pfad zum Projektverzeichnis
        scenario_path: Pfad zum Szenarioverzeichnis
        
    Returns:
        bool: True wenn gültig, False sonst
    """
    try:
        with LoggedOperation("Projektstruktur validieren"):
            # Überprüfe Projektverzeichnis
            if not project_path.exists():
                logger.error(f"❌ Projektverzeichnis nicht gefunden: {project_path}")
                return False
                
            # Überprüfe Szenarioverzeichnis
            if not scenario_path.exists():
                logger.error(f"❌ Szenarioverzeichnis nicht gefunden: {scenario_path}")
                return False
                
            # Überprüfe erforderliche Verzeichnisse
            required_dirs = [
                'inputs/building-geometry',
                'inputs/building-properties',
                'inputs/networks',
                'outputs/data'
            ]
            
            for dir_path in required_dirs:
                full_path = scenario_path / dir_path
                if not full_path.exists():
                    logger.error(f"❌ Erforderliches Verzeichnis nicht gefunden: {full_path}")
                    return False
                    
            # Überprüfe erforderliche Dateien
            required_files = [
                'inputs/building-geometry/zone.shp',
                'inputs/building-geometry/site.shp',
                'inputs/building-geometry/surroundings.shp',
                'inputs/building-properties/typology.dbf',
                'inputs/networks/streets.shp'
            ]
            
            for file_path in required_files:
                full_path = scenario_path / file_path
                if not full_path.exists():
                    logger.error(f"❌ Erforderliche Datei nicht gefunden: {full_path}")
                    return False
                    
            logger.info("✅ Projektstruktur erfolgreich validiert")
            return True
            
    except Exception as e:
        logger.error(f"❌ Fehler bei der Validierung der Projektstruktur: {str(e)}")
        return False

def setup_project_structure(project_path: Path, scenario_path: Path) -> Dict[str, Path]:
    """Erstellt die CEA-Projektstruktur
    
    Args:
        project_path: Pfad zum Projektverzeichnis
        scenario_path: Pfad zum Szenarioverzeichnis
        
    Returns:
        Dict[str, Path]: Dictionary mit den Pfaden der erstellten Verzeichnisse
    """
    try:
        with LoggedOperation("Projektstruktur erstellen"):
            # Erstelle Backup wenn nötig
            if scenario_path.exists():
                backup_path = create_backup(scenario_path)
                if backup_path:
                    logger.info(f"✅ Backup erstellt in: {backup_path}")
            
            # Definiere Verzeichnisstruktur
            dirs = {
                'inputs': {
                    'building-geometry': ['zone.shp', 'site.shp', 'surroundings.shp'],
                    'building-properties': ['typology.dbf'],
                    'networks': ['streets.shp']
                },
                'outputs': {
                    'data': ['zone_enriched.geojson']
                }
            }
            
            # Erstelle Verzeichnisse
            created_dirs = {}
            for parent, children in dirs.items():
                parent_path = scenario_path / parent
                parent_path.mkdir(parents=True, exist_ok=True)
                created_dirs[parent] = parent_path
                
                for child, files in children.items():
                    child_path = parent_path / child
                    child_path.mkdir(parents=True, exist_ok=True)
                    created_dirs[f"{parent}_{child}"] = child_path
                    
                    # Erstelle leere Dateien
                    for file in files:
                        file_path = child_path / file
                        if not file_path.exists():
                            file_path.touch()
            
            # Validiere Projektstruktur
            if not validate_project_structure(project_path, scenario_path):
                raise ValueError("Projektstruktur konnte nicht validiert werden")
                
            logger.info("✅ Projektstruktur erfolgreich erstellt")
            return created_dirs
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Erstellen der Projektstruktur: {str(e)}")
        raise

def ensure_directories(config: Dict[str, Any]) -> None:
    """
    Stellt sicher, dass alle benötigten Verzeichnisse existieren.
    
    Args:
        config: Projektkonfiguration
    """
    project_path = Path(config.get('project', {}).get('path', '.'))
    project_dirs = config.get('project', {}).get('directories', {})
    
    for dir_type, subdirs in project_dirs.items():
        base_dir = project_path / dir_type
        base_dir.mkdir(parents=True, exist_ok=True)
        
        if isinstance(subdirs, list):
            for subdir in subdirs:
                subdir_path = base_dir / subdir
                subdir_path.mkdir(parents=True, exist_ok=True)
        elif isinstance(subdirs, str):
            subdir_path = base_dir / subdirs
            subdir_path.mkdir(parents=True, exist_ok=True)

def load_configs() -> Dict[str, Any]:
    """
    Lädt alle Konfigurationsdateien.
    
    Returns:
        Dict[str, Any]: Geladene Konfigurationen
    """
    configs = {
        "project": {
            "name": "CEA Wien",
            "version": "1.0.0"
        }
    }
    
    return configs 
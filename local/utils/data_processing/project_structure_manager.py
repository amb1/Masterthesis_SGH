import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

class ProjectStructureManager:
    """Klasse für die Verwaltung der CEA-Projektstruktur"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den ProjectStructureManager
        
        Args:
            config (Dict[str, Any]): Konfigurationsdictionary
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_project_structure(self, project_path: Path, scenario_path: Path) -> Dict[str, Path]:
        """Erstellt die CEA-Projektstruktur
        
        Args:
            project_path (Path): Pfad zum Projektverzeichnis
            scenario_path (Path): Pfad zum Szenarioverzeichnis
            
        Returns:
            Dict[str, Path]: Dictionary mit den Pfaden der erstellten Verzeichnisse
        """
        try:
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
                            
            self.logger.info("✅ Projektstruktur erfolgreich erstellt")
            return created_dirs
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen der Projektstruktur: {str(e)}")
            raise
            
    def validate_project_structure(self, project_path: Path, scenario_path: Path) -> bool:
        """Überprüft die CEA-Projektstruktur
        
        Args:
            project_path (Path): Pfad zum Projektverzeichnis
            scenario_path (Path): Pfad zum Szenarioverzeichnis
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            # Überprüfe Projektverzeichnis
            if not project_path.exists():
                self.logger.error(f"❌ Projektverzeichnis nicht gefunden: {project_path}")
                return False
                
            # Überprüfe Szenarioverzeichnis
            if not scenario_path.exists():
                self.logger.error(f"❌ Szenarioverzeichnis nicht gefunden: {scenario_path}")
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
                    self.logger.error(f"❌ Erforderliches Verzeichnis nicht gefunden: {full_path}")
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
                    self.logger.error(f"❌ Erforderliche Datei nicht gefunden: {full_path}")
                    return False
                    
            self.logger.info("✅ Projektstruktur erfolgreich validiert")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Validierung der Projektstruktur: {str(e)}")
            return False
            
    def get_file_path(self, scenario_path: Path, file_type: str) -> Optional[Path]:
        """Gibt den Pfad für eine bestimmte Datei zurück
        
        Args:
            scenario_path (Path): Pfad zum Szenarioverzeichnis
            file_type (str): Typ der Datei (z.B. 'zone.shp', 'typology.dbf')
            
        Returns:
            Optional[Path]: Pfad zur Datei oder None
        """
        try:
            # Mapping von Dateitypen zu Verzeichnissen
            file_mapping = {
                'zone.shp': 'inputs/building-geometry',
                'site.shp': 'inputs/building-geometry',
                'surroundings.shp': 'inputs/building-geometry',
                'typology.dbf': 'inputs/building-properties',
                'streets.shp': 'inputs/networks',
                'zone_enriched.geojson': 'outputs/data'
            }
            
            if file_type not in file_mapping:
                self.logger.error(f"❌ Unbekannter Dateityp: {file_type}")
                return None
                
            file_path = scenario_path / file_mapping[file_type] / file_type
            if not file_path.exists():
                self.logger.warning(f"⚠️ Datei nicht gefunden: {file_path}")
                return None
                
            return file_path
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen des Dateipfads: {str(e)}")
            return None
            
    def create_backup(self, scenario_path: Path) -> Optional[Path]:
        """Erstellt ein Backup des Szenarios
        
        Args:
            scenario_path (Path): Pfad zum Szenarioverzeichnis
            
        Returns:
            Optional[Path]: Pfad zum Backup-Verzeichnis oder None
        """
        try:
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
                    
            self.logger.info(f"✅ Backup erstellt: {backup_dir}")
            return backup_dir
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen des Backups: {str(e)}")
            return None
            
    def cleanup_project(self, project_path: Path) -> bool:
        """Bereinigt das Projektverzeichnis
        
        Args:
            project_path (Path): Pfad zum Projektverzeichnis
            
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Lösche temporäre Dateien
            temp_files = list(project_path.rglob('*.tmp'))
            for temp_file in temp_files:
                temp_file.unlink()
                
            # Lösche leere Verzeichnisse
            for dir_path in project_path.rglob('*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    
            self.logger.info("✅ Projektverzeichnis bereinigt")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Projektbereinigung: {str(e)}")
            return False 
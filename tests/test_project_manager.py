"""
Unit-Tests für das Projektmanagement-Modul.

Testet die Funktionalität des project_manager Moduls für CEA-Projekte.
"""

import unittest
import pytest
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch, MagicMock
import sys
from argparse import Namespace
from core.project_manager import (
    ProjectManager,
    get_project_info,
    create_backup,
    cleanup_project,
    validate_project_structure,
    setup_project_structure,
    ensure_directories,
    load_configs
)

# Füge das Hauptverzeichnis zum Python-Path hinzu
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

class TestProjectManager(unittest.TestCase):
    """Testklasse für das Projektmanagement-Modul"""
    
    def setUp(self):
        """Wird vor jedem Test ausgeführt"""
        # Erstelle temporäres Verzeichnis
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_name = "test_project"
        self.scenario_name = "test_scenario"
        self.project_path = self.temp_dir / "projects" / self.project_name
        self.scenario_path = self.project_path / self.scenario_name
        
    def tearDown(self):
        """Wird nach jedem Test ausgeführt"""
        # Lösche temporäres Verzeichnis
        shutil.rmtree(self.temp_dir)
        
    def test_get_project_info_with_args(self):
        """Test: get_project_info mit Kommandozeilenargumenten"""
        args = Namespace(
            project_name=self.project_name,
            scenario_name=self.scenario_name,
            force=True
        )
        
        project_name, scenario_name, project_path, scenario_path = get_project_info(args)
        
        self.assertEqual(project_name, self.project_name)
        self.assertEqual(scenario_name, self.scenario_name)
        self.assertEqual(project_path, Path("projects") / self.project_name)
        self.assertEqual(scenario_path, project_path / self.scenario_name)
        
    @patch('builtins.input')
    def test_get_project_info_interactive(self, mock_input):
        """Test: get_project_info im interaktiven Modus"""
        mock_input.side_effect = [self.project_name, self.scenario_name]
        
        project_name, scenario_name, project_path, scenario_path = get_project_info()
        
        self.assertEqual(project_name, self.project_name)
        self.assertEqual(scenario_name, self.scenario_name)
        self.assertEqual(project_path, Path("projects") / self.project_name)
        self.assertEqual(scenario_path, project_path / self.scenario_name)
        
    def test_create_backup(self):
        """Test: create_backup erstellt ein Backup des Szenarios"""
        # Erstelle Testdateien
        self.scenario_path.mkdir(parents=True)
        test_file = self.scenario_path / "test.txt"
        test_file.write_text("Test content")
        
        backup_path = create_backup(self.scenario_path)
        
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())
        self.assertTrue((backup_path / "test.txt").exists())
        self.assertEqual((backup_path / "test.txt").read_text(), "Test content")
        
    def test_cleanup_project(self):
        """Test: cleanup_project entfernt temporäre Dateien und leere Verzeichnisse"""
        # Erstelle temporäre Dateien und leere Verzeichnisse
        self.project_path.mkdir(parents=True)
        temp_file = self.project_path / "test.tmp"
        temp_file.write_text("Temporary content")
        empty_dir = self.project_path / "empty_dir"
        empty_dir.mkdir()
        
        result = cleanup_project(self.project_path)
        
        self.assertTrue(result)
        self.assertFalse(temp_file.exists())
        self.assertFalse(empty_dir.exists())
        
    def test_validate_project_structure_valid(self):
        """Test: validate_project_structure mit gültiger Struktur"""
        # Erstelle gültige Projektstruktur
        dirs = setup_project_structure(self.project_path, self.scenario_path)
        
        result = validate_project_structure(self.project_path, self.scenario_path)
        
        self.assertTrue(result)
        
    def test_validate_project_structure_invalid(self):
        """Test: validate_project_structure mit ungültiger Struktur"""
        result = validate_project_structure(self.project_path, self.scenario_path)
        
        self.assertFalse(result)
        
    def test_setup_project_structure(self):
        """Test: setup_project_structure erstellt die Projektstruktur"""
        dirs = setup_project_structure(self.project_path, self.scenario_path)
        
        self.assertIsInstance(dirs, dict)
        self.assertTrue(self.project_path.exists())
        self.assertTrue(self.scenario_path.exists())
        
        # Überprüfe erforderliche Verzeichnisse
        required_dirs = [
            'inputs/building-geometry',
            'inputs/building-properties',
            'inputs/networks',
            'outputs/data'
        ]
        
        for dir_path in required_dirs:
            self.assertTrue((self.scenario_path / dir_path).exists())
            
        # Überprüfe erforderliche Dateien
        required_files = [
            'inputs/building-geometry/zone.shp',
            'inputs/building-geometry/site.shp',
            'inputs/building-geometry/surroundings.shp',
            'inputs/building-properties/typology.dbf',
            'inputs/networks/streets.shp'
        ]
        
        for file_path in required_files:
            self.assertTrue((self.scenario_path / file_path).exists())

if __name__ == '__main__':
    unittest.main() 
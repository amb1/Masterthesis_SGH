"""
Unit-Tests für die Projekt-Utilities.
"""

import unittest
import pytest
import shutil
from pathlib import Path

from core.project_manager import (
    get_project_info,
    create_backup,
    cleanup_project,
    validate_project_structure,
    setup_project_structure,
    ensure_directories,
    load_configs
)

@pytest.fixture
def temp_project_dir(tmp_path):
    """Erstellt ein temporäres Projektverzeichnis."""
    return tmp_path / "test_project"

@pytest.fixture
def temp_scenario_dir(temp_project_dir):
    """Erstellt ein temporäres Szenario-Verzeichnis."""
    scenario_dir = temp_project_dir / "scenarios" / "test_scenario"
    scenario_dir.mkdir(parents=True)
    return scenario_dir

@pytest.fixture
def sample_config(temp_project_dir):
    """Beispielkonfiguration für Tests."""
    return {
        'project': {
            'name': 'Test Project',
            'directories': {
                'inputs': ['buildings', 'weather'],
                'outputs': ['data', 'plots'],
                'temp': 'temp'
            }
        },
        'cea_workflow': {
            'scripts': [
                {
                    'name': 'radiation',
                    'parameters': {
                        'weather': 'Zug'
                    }
                }
            ]
        }
    }

def test_get_project_info():
    """Test get_project_info."""
    info = get_project_info()
    assert isinstance(info, dict)
    assert 'project_name' in info
    assert 'scenario_name' in info

def test_create_backup(temp_project_dir):
    """Test create_backup mit temporärem Verzeichnis."""
    # Erstelle Testdateien
    test_file = temp_project_dir / "test.txt"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("Test")
    
    backup_dir = create_backup(temp_project_dir)
    assert backup_dir is not None
    assert backup_dir.exists()
    assert (backup_dir / "test.txt").exists()

def test_cleanup_project(temp_project_dir):
    """Test cleanup_project mit temporärem Verzeichnis."""
    # Erstelle temporäre Dateien
    temp_file = temp_project_dir / "temp.txt"
    temp_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file.write_text("Temporary")
    
    success = cleanup_project(temp_project_dir)
    assert success
    assert not temp_file.exists()

def test_validate_project_structure(temp_project_dir):
    """Test validate_project_structure mit gültiger Struktur."""
    # Erstelle Projektstruktur
    for dir_name in ['inputs', 'outputs', 'databases']:
        (temp_project_dir / dir_name).mkdir(parents=True, exist_ok=True)
    
    # Erstelle Szenarioverzeichnis
    scenario_dir = temp_project_dir / "scenario"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    
    assert validate_project_structure(temp_project_dir, scenario_dir)

def test_validate_project_structure_invalid(temp_project_dir):
    """Test validate_project_structure mit ungültiger Struktur."""
    assert not validate_project_structure(temp_project_dir, temp_project_dir / "scenario")

def test_setup_project_structure(temp_project_dir):
    """Test setup_project_structure."""
    created_dirs = setup_project_structure(temp_project_dir, temp_project_dir / "scenario")
    assert isinstance(created_dirs, dict)
    assert all(path.exists() for path in created_dirs.values())

def test_ensure_directories(temp_project_dir, sample_config):
    """Test ensure_directories mit Konfiguration."""
    # Setze den Projektpfad in der Konfiguration
    sample_config['project']['path'] = str(temp_project_dir)
    
    ensure_directories(sample_config)
    
    # Überprüfe die Verzeichnisstruktur
    for dir_type in ["inputs", "outputs"]:
        base_dir = temp_project_dir / dir_type
        assert base_dir.exists()
        for subdir in sample_config["project"]["directories"][dir_type]:
            assert (base_dir / subdir).exists()
    
    # Überprüfe das temp-Verzeichnis
    temp_dir = temp_project_dir / sample_config["project"]["directories"]["temp"]
    assert temp_dir.exists()

def test_load_configs():
    """Test load_configs."""
    configs = load_configs()
    assert isinstance(configs, dict)
    assert 'project' in configs
    assert 'name' in configs['project']
    assert 'version' in configs['project']

@pytest.mark.parametrize("missing_dir", ["inputs", "outputs", "databases"])
def test_validate_project_structure_missing_dirs(temp_project_dir, missing_dir):
    """Test validate_project_structure mit fehlenden Verzeichnissen."""
    # Erstelle alle Verzeichnisse außer dem fehlenden
    for dir_name in ['inputs', 'outputs', 'databases']:
        if dir_name != missing_dir:
            (temp_project_dir / dir_name).mkdir(parents=True, exist_ok=True)
    
    assert not validate_project_structure(temp_project_dir, temp_project_dir / "scenario") 
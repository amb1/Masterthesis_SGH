"""
Fixtures für Projekt-bezogene Tests.

Dieses Modul enthält wiederverwendbare Fixtures für Tests der Projektmanagement-Funktionalität.
"""

import pytest
from pathlib import Path
import shutil
import yaml

@pytest.fixture
def temp_project_dir(tmp_path):
    """Erstellt ein temporäres Projektverzeichnis für Tests."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir

@pytest.fixture
def sample_project_structure(temp_project_dir):
    """Erstellt eine Beispiel-Projektstruktur für Tests."""
    dirs = [
        'input/buildings',
        'input/surroundings',
        'input/streets',
        'output/data',
        'output/plots',
        'config'
    ]
    
    for dir_path in dirs:
        (temp_project_dir / dir_path).mkdir(parents=True)
    
    return temp_project_dir

@pytest.fixture
def sample_config_file(temp_project_dir):
    """Erstellt eine Beispiel-Konfigurationsdatei für Tests."""
    config_data = {
        'project': {
            'name': 'test_project',
            'scenario': 'baseline'
        },
        'paths': {
            'input': str(temp_project_dir / 'input'),
            'output': str(temp_project_dir / 'output'),
            'config': str(temp_project_dir / 'config')
        }
    }
    
    config_file = temp_project_dir / 'config' / 'config.yml'
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    return config_file

@pytest.fixture
def cleanup_project(temp_project_dir):
    """Fixture für das Aufräumen nach den Tests."""
    yield
    if temp_project_dir.exists():
        shutil.rmtree(temp_project_dir) 
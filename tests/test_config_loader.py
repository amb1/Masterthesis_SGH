"""Tests für das Config-Loader-Modul."""
import pytest
import os
import yaml
from core.config_manager import load_config, validate_config

@pytest.fixture
def sample_config_file(tmp_path):
    """Erstellt eine temporäre Konfigurations-Datei."""
    config = {
        "cea_workflow": {
            "scripts": [
                {
                    "name": "data-initializer",
                    "parameters": {
                        "databases": ["archetypes", "assemblies"]
                    }
                },
                {
                    "name": "weather-helper",
                    "parameters": {
                        "weather": "Zuerich-Kloten_2030_AB1_TMY.epw"
                    }
                }
            ]
        }
    }
    
    config_file = tmp_path / "test_config.yml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    
    return config_file

def test_load_config(sample_config_file):
    """Test das Laden einer Konfigurationsdatei."""
    config = load_config(sample_config_file)
    
    assert "cea_workflow" in config
    assert len(config["cea_workflow"]["scripts"]) == 2
    assert config["cea_workflow"]["scripts"][0]["name"] == "data-initializer"

def test_load_nonexistent_config():
    """Test das Laden einer nicht existierenden Konfigurationsdatei."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yml")

def test_validate_config(sample_config_file):
    """Test die Konfigurationsvalidierung."""
    config = load_config(sample_config_file)
    validation_result = validate_config(config)
    
    assert validation_result.is_valid
    assert len(validation_result.errors) == 0

def test_validate_invalid_config():
    """Test die Validierung einer ungültigen Konfiguration."""
    invalid_config = {
        "cea_workflow": {
            "scripts": [
                {
                    "parameters": {}  # Fehlendes required 'name' Feld
                }
            ]
        }
    }
    
    validation_result = validate_config(invalid_config)
    assert not validation_result.is_valid
    assert len(validation_result.errors) > 0

@pytest.mark.parametrize("config_file,expected_error", [
    ("invalid.json", "Ungültiges Dateiformat"),
    ("empty.yml", "Leere Konfigurationsdatei"),
    ("malformed.yml", "YAML Syntax-Fehler")
])
def test_load_config_errors(tmp_path, config_file, expected_error):
    """Test verschiedene Fehlerfälle beim Laden der Konfiguration."""
    file_path = tmp_path / config_file
    
    if config_file == "invalid.json":
        with open(file_path, "w") as f:
            f.write("{invalid json}")
    elif config_file == "empty.yml":
        open(file_path, "w").close()
    elif config_file == "malformed.yml":
        with open(file_path, "w") as f:
            f.write("key: [missing bracket")
    
    with pytest.raises(Exception) as exc_info:
        load_config(file_path)
    assert expected_error in str(exc_info.value) 
import yaml
from pathlib import Path

def load_config(config_path):
    """Lädt die Konfiguration aus einer YAML-Datei
    
    Args:
        config_path: Pfad zur Konfigurationsdatei
    """
    try:
        print(f"Lade Konfiguration: {config_path.name}")
        
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            
        return config
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
        return None 
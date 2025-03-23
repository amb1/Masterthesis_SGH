"""
Erstellt die Verzeichnisstruktur für die Pipeline
"""
from pathlib import Path

def create_pipeline_structure():
    """Erstellt die Pipeline-Verzeichnisstruktur"""
    base_dir = Path(__file__).parent
    
    # Hauptmodule
    modules = [
        'converters',
        'extractors',
        'storage',
        'visualization'
    ]
    
    # Erstelle Hauptmodule
    for module in modules:
        (base_dir / module).mkdir(exist_ok=True)
        
    # Erstelle Tests-Verzeichnis
    tests_dir = base_dir / 'tests'
    tests_dir.mkdir(exist_ok=True)
    
    # Erstelle Test-Unterverzeichnisse
    for module in modules + ['fixtures']:
        (tests_dir / module).mkdir(exist_ok=True)
        
    # Erstelle __init__.py Dateien
    for module in modules:
        (base_dir / module / '__init__.py').touch()
        (tests_dir / module / '__init__.py').touch()
    
    # Erstelle base.py wenn nicht vorhanden
    if not (base_dir / 'base.py').exists():
        (base_dir / 'base.py').touch()
    
    print("Pipeline-Verzeichnisstruktur erfolgreich erstellt!")

if __name__ == '__main__':
    create_pipeline_structure() 
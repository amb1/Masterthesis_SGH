import os
import shutil

def create_mdc_structure():
    """Erstellt die Verzeichnisstruktur für MDC-Dateien."""
    
    # Basis-Verzeichnisse
    directories = [
        '.cursor/rules/base',
        '.cursor/rules/components/atoms',
        '.cursor/rules/components/molecules',
        '.cursor/rules/components/organisms',
        '.cursor/rules/meta'
    ]
    
    # Erstelle Verzeichnisse
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Verzeichnis erstellt: {directory}")
    
    # Verschiebe und bereinige Dateien
    file_moves = {
        # Basis MDC-Dateien
        'pipeline-structure.mdc': 'base/050-pipeline.mdc',
        'testing-strategy.mdc': 'base/060-testing.mdc',
        
        # Zu löschende Dateien (nach Integration)
        'base-guidelines.mdc': None,
        'naming-conventions.mdc': None,
        'component-structure.mdc': None
    }
    
    for source, dest in file_moves.items():
        src_path = os.path.join('.cursor/rules', source)
        if os.path.exists(src_path):
            if dest is None:
                os.remove(src_path)
                print(f"✓ MDC-Datei gelöscht: {source}")
            else:
                dst_path = os.path.join('.cursor/rules', dest)
                shutil.move(src_path, dst_path)
                print(f"✓ MDC-Datei verschoben: {source} → {dest}")
    
    print("\n✨ MDC-Verzeichnisstruktur erfolgreich bereinigt!")

if __name__ == '__main__':
    create_mdc_structure() 
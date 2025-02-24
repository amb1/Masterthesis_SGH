from owslib.wfs import WebFeatureService
import yaml
from pathlib import Path

def get_wfs_layer_count() -> int:
    """
    Gibt die Anzahl der verfügbaren WFS Layer des Wien Geodatenservices zurück
    
    Returns:
        int: Anzahl der verfügbaren Layer
    """
    try:
        wfs_url = 'https://data.wien.gv.at/daten/geo'
        wfs_version = '1.1.0'
        
        wfs = WebFeatureService(url=wfs_url, version=wfs_version)
        return len(wfs.contents)
            
    except Exception as e:
        print(f"Fehler bei WFS-Analyse: {str(e)}")
        return 0

def analyze_wfs_layers():
    """Analysiert die verfügbaren WFS Layer des Wien Geodatenservices"""
    try:
        wfs_url = 'https://data.wien.gv.at/daten/geo'
        wfs_version = '1.1.0'
        
        print(f"Verbinde mit WFS-Service: {wfs_url}")
        wfs = WebFeatureService(url=wfs_url, version=wfs_version)
        
        layer_count = len(wfs.contents)
        print(f"\nAnzahl verfügbarer Layer: {layer_count}")
        
        print("\nVerfügbare WFS Layer:")
        for layer in sorted(wfs.contents):
            print(f"- {layer}")
            
        # Optional: Speichere Layer-Liste in YAML
        output_path = Path(__file__).resolve().parent.parent.parent.parent / "cfg" / "data_sources" / "available_wfs_layers.yml"
        
        layers_dict = {
            "available_layers": sorted(wfs.contents)
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(layers_dict, f, allow_unicode=True)
            
        print(f"\nLayer-Liste gespeichert in: {output_path}")
            
    except Exception as e:
        print(f"Fehler bei WFS-Analyse: {str(e)}")

if __name__ == "__main__":
    layer_count = get_wfs_layer_count()
    print(f"Anzahl verfügbarer WFS Layer: {layer_count}") 
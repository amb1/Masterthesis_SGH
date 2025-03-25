from pathlib import Path
import logging
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor

# Konfiguriere Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Konfiguration
    config = {
        'validation': {
            'min_area': 1.0,  # Minimale Fläche in m²
            'max_angle': 80.0  # Maximaler Dachwinkel in Grad
        }
    }
    
    # Pfade
    input_file = Path('data/raw/citygml/099082.gml')
    output_dir = Path('data/processed/3dtiles/099082')
    
    # Erstelle Prozessor
    processor = CityGMLBuildingProcessor(config)
    
    # Verarbeite CityGML
    logger.info(f"Verarbeite {input_file}...")
    buildings = processor.process_citygml(input_file)
    
    if len(buildings) > 0:
        logger.info(f"{len(buildings)} Gebäude gefunden")
        
        # Exportiere als 3D Tiles
        logger.info(f"Exportiere nach {output_dir}...")
        if processor.export_to_3dtiles(buildings, output_dir):
            logger.info("✅ Export erfolgreich")
        else:
            logger.error("❌ Fehler beim Export")
    else:
        logger.warning("Keine Gebäude gefunden")

if __name__ == "__main__":
    main() 
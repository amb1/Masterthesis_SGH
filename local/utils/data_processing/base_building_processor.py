import sys
import logging
from pathlib import Path

# Setze den Projekt-Root als Suchpfad für Module
# sys.path.append(str(Path(__file__).resolve().parent))
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# from utils.data_sources.fetch_geojson_buildings import fetch_geojson_buildings
from utils.data_sources.fetch_wfs_data import fetch_wfs_data
from utils.data_sources.fetch_osm_buildings import fetch_osm_buildings
from utils.data_sources.fetch_osm_streets import fetch_osm_streets
from utils.data_processing.create_site_polygon import create_site_polygon
from utils.data_processing.cea_building_processor import CEABuildingProcessor

class BaseBuildingProcessor:
    """Basis-Klasse für die Verarbeitung von Gebäuden"""
    
    def __init__(self, config: dict):
        """Initialisiert den Building Processor.
        
        Args:
            config (dict): Die Konfiguration
        """
        self.config = config
        self.file_formats = config.get('file_formats', {})
        self.paths = config.get('paths', {})
        self.setup_logger()

    def process_building(self, building: dict) -> dict:
        """Verarbeitet ein einzelnes Gebäude.
        
        Args:
            building (dict): Die Gebäudeinformationen
            
        Returns:
            dict: Die verarbeiteten Gebäudeinformationen
        """
        raise NotImplementedError("Diese Methode muss von der Unterklasse implementiert werden")
        
    def validate_building(self, building: dict) -> bool:
        """Überprüft, ob ein Gebäude gültig ist.
        
        Args:
            building (dict): Die Gebäudeinformationen
            
        Returns:
            bool: True wenn das Gebäude gültig ist, False sonst
        """
        required_fields = ['building_id', 'geometry']
        return all(field in building for field in required_fields)

    def process_buildings(self, input_path, output_path, input_format="geojson"):
        """Zentrale Methode zur Verarbeitung von Gebäudedaten"""
        try:
            self.logger.info(f"Starte Verarbeitung für {input_format.upper()} Daten...")

            if input_format == "citygml":
                self.logger.info("📡 Lade CityGML-Daten...")
                buildings_df = fetch_citygml_buildings(input_path, self.config)
                buildings_df = fetch_wfs_data(buildings_df)
            else:
                self.logger.info("Lade GeoJSON-Daten...")
                buildings_df = fetch_geojson_buildings(input_path, self.config)

            self.logger.info("Erstelle Standortpolygon...")
            site_polygon = create_site_polygon(buildings_df)

            self.logger.info("Füge OSM-Gebäudedaten hinzu...")
            buildings_df = fetch_osm_buildings(buildings_df, site_polygon)

            self.logger.info("Füge OSM-Straßendaten hinzu...")
            buildings_df = fetch_osm_streets(buildings_df, site_polygon)

            self.logger.info("Verarbeite Gebäude mit dem CEA-Processor...")
            self.cea_processor.process_cea(buildings_df, output_path)

            self.logger.info(f"👍Verarbeitung abgeschlossen für {input_format.upper()} Daten")

            return buildings_df

        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Gebäude-Verarbeitung: {str(e)}", exc_info=True)
            raise

    def setup_logger(self):
        """Richtet einen Logger für den BaseBuildingProcessor ein"""
        self.logger = logging.getLogger(self.__class__.__name__)

        if not self.logger.hasHandlers():  # Verhindert doppelte Handler
            self.logger.setLevel(logging.DEBUG)

            # Erstelle den Konsolen-Handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)

            # Definiere das Log-Format
            log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s: %(message)s')
            console_handler.setFormatter(log_format)

            # Füge den Handler hinzu
            self.logger.addHandler(console_handler)

        # Stille die Logger von Bibliotheken, um Spam zu vermeiden
        logging.getLogger("shapely").setLevel(logging.WARNING)
        logging.getLogger("geopandas").setLevel(logging.WARNING)
        logging.getLogger("fiona").setLevel(logging.WARNING)
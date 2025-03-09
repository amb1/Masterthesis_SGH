import sys
from pathlib import Path
import logging
import geopandas as gpd
import pandas as pd
import yaml

# Füge Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from utils.data_processing.cea_building_processor import CEABuildingProcessor
from utils.data_sources.fetch_citygml_buildings import fetch_citygml_buildings
from utils.data_sources.fetch_wfs_data import ViennaWFS

# Konfiguriere Logger
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def load_test_config():
    """Lädt die Testkonfiguration"""
    try:
        config = {
            'metrics_config': 'cfg/cea/building_metrics.yml',
            'crs': 'EPSG:31256',
            'citygml': {
                'namespaces': {
                    'bldg': 'http://www.opengis.net/citygml/building/2.0',
                    'gml': 'http://www.opengis.net/gml',
                    'gen': 'http://www.opengis.net/citygml/generics/2.0'
                }
            },
            'wfs': {
                'url': 'https://data.wien.gv.at/daten/wfs',
                'version': '2.0.0',
                'timeout': 30,
                'crs': 'EPSG:31256'
            }
        }
        return config
    except Exception as e:
        logger.error(f"❌ Fehler beim Laden der Testkonfiguration: {str(e)}")
        return None

def test_cea_processor():
    """Testet die CEA-Prozessor Funktionalität"""
    try:
        logger.info("\n🔍 Starte CEA-Prozessor Test...")
        
        # Lade Konfiguration
        config = load_test_config()
        if not config:
            return False
        
        # Erstelle CEA-Prozessor
        processor = CEABuildingProcessor(config)
        logger.info("✅ CEA-Prozessor erstellt")
        
        # Lade CityGML-Gebäude
        citygml_path = root_dir / "data" / "inputs" / "citygml" / "099082.gml"
        if not citygml_path.exists():
            logger.error(f"❌ CityGML-Datei nicht gefunden: {citygml_path}")
            return False
            
        buildings_gdf = fetch_citygml_buildings(str(citygml_path), config)
        if buildings_gdf is None:
            logger.error("❌ Fehler beim Laden der CityGML-Gebäude")
            return False
            
        logger.info(f"✅ {len(buildings_gdf)} Gebäude aus CityGML geladen")
        
        # Lade WFS-Daten für Test
        wfs_config = config.get('wfs', {})
        wfs = ViennaWFS(
            url=wfs_config.get('url', 'https://data.wien.gv.at/daten/wfs'),
            version=wfs_config.get('version', '2.0.0'),
            timeout=wfs_config.get('timeout', 30),
            crs=wfs_config.get('crs', 'EPSG:31256')
        )
        
        # Konfiguriere WFS-Layer
        layer_config = {
            'layer_pattern': 'ogdwien:FMZKGEBOGD',  # Beispiel Layer für Gebäude
            'attributes': ['OBJECTID', 'TYP', 'NUTZUNG']
        }
        
        wfs_data = wfs.fetch_data(layer_config)
        if wfs_data is None:
            logger.warning("⚠️ Keine WFS-Daten verfügbar")
        else:
            logger.info(f"✅ WFS-Daten geladen")
        
        # Teste Gebäudeverarbeitung
        processor.load_citygml_buildings(buildings_gdf)
        
        # Verarbeite jedes Gebäude
        for idx, building in buildings_gdf.iterrows():
            if processor.validate_building(building):
                processed = processor.process_building(building)
                if processed:
                    logger.info(f"✅ Gebäude {idx} erfolgreich verarbeitet")
                else:
                    logger.warning(f"⚠️ Fehler bei Gebäude {idx}")
        
        # Berechne Metriken
        enriched_buildings = processor.calculate_metrics()
        if enriched_buildings is None:
            logger.error("❌ Fehler bei der Metrikberechnung")
            return False
            
        logger.info("\n📊 Berechnete Metriken:")
        logger.info(f"- Anzahl Gebäude: {len(enriched_buildings)}")
        logger.info(f"- Verfügbare Spalten: {enriched_buildings.columns.tolist()}")
        
        # Speichere Ergebnisse
        output_path = root_dir / "tests" / "output" / "test_buildings.geojson"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        enriched_buildings.to_file(output_path, driver='GeoJSON')
        logger.info(f"\n💾 Ergebnisse gespeichert nach: {output_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler im Test: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_cea_processor()
    if success:
        logger.info("\n✅ CEA-Prozessor Test erfolgreich abgeschlossen!")
    else:
        logger.error("\n❌ CEA-Prozessor Test fehlgeschlagen!") 
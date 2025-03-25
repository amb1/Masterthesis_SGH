"""
CityGML-Fetcher für die Verarbeitung von CityGML-Daten aus Wien.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
import geopandas as gpd
import pandas as pd

from .config import CityGMLConfig, CityGMLConfigError
from .client import CityGMLBaseClient
from .geometry import CityGMLGeometryProcessor
from .attributes import CityGMLAttributeProcessor

class ViennaCityGMLFetcher:
    """Fetcher für CityGML-Daten aus Wien."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """Initialisiert den Vienna CityGML Fetcher.
        
        Args:
            config: Optional[Dict] - Direkte Konfiguration
            config_path: Optional[str] - Pfad zur Konfigurationsdatei
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialisiere Konfiguration
        self.config = CityGMLConfig(config=config, config_path=config_path)
        if not self.config.validate():
            raise CityGMLConfigError("Ungültige CityGML-Konfiguration")
            
        # Initialisiere Komponenten
        self.client = CityGMLBaseClient(namespaces=self.config.namespaces)
        self.geometry_processor = CityGMLGeometryProcessor(
            config=self.config.geometry_config,
            namespaces=self.config.namespaces
        )
        self.attribute_processor = CityGMLAttributeProcessor(
            config=self.config.config,
            namespaces=self.config.namespaces
        )
        
    def process_citygml(self, citygml_path: Path) -> Optional[gpd.GeoDataFrame]:
        """Verarbeitet eine CityGML-Datei und extrahiert Gebäudedaten.
        
        Args:
            citygml_path: Path - Pfad zur CityGML-Datei
            
        Returns:
            Optional[gpd.GeoDataFrame]: GeoDataFrame mit Gebäudedaten oder None bei Fehler
        """
        try:
            # Lade CityGML-Datei
            root = self.client.load_citygml(citygml_path)
            if root is None:
                return None
                
            # Finde alle Gebäude
            buildings = self.client.find_buildings(root)
            if not buildings:
                self.logger.warning("⚠️ Keine Gebäude gefunden")
                return None
                
            # Verarbeite Gebäude
            building_data = []
            geometries = []
            
            # Statistiken
            stats = {
                'total': len(buildings),
                'success': 0,
                'failed': 0,
                'geometry': {
                    'success': 0,
                    'failed': 0,
                    'total_area': 0,
                    'min_area': float('inf'),
                    'max_area': 0,
                    'polygons': 0,
                    'multipolygons': 0
                },
                'attributes': {
                    'success': 0,
                    'failed': 0,
                    'missing_fields': {}
                }
            }
            
            for building in buildings:
                try:
                    # Extrahiere Geometrie
                    footprint = self.geometry_processor.extract_building_footprint(building)
                    if footprint is None:
                        stats['geometry']['failed'] += 1
                        continue
                        
                    # Aktualisiere Geometrie-Statistiken
                    stats['geometry']['success'] += 1
                    area = footprint.area
                    stats['geometry']['total_area'] += area
                    stats['geometry']['min_area'] = min(stats['geometry']['min_area'], area)
                    stats['geometry']['max_area'] = max(stats['geometry']['max_area'], area)
                    
                    if hasattr(footprint, 'geoms'):
                        stats['geometry']['multipolygons'] += 1
                    else:
                        stats['geometry']['polygons'] += 1
                        
                    # Extrahiere Attribute
                    attributes = self.attribute_processor.extract_building_attributes(building)
                    if attributes is None:
                        stats['attributes']['failed'] += 1
                        continue
                        
                    # Aktualisiere Attribut-Statistiken
                    stats['attributes']['success'] += 1
                    
                    # Füge Daten hinzu
                    building_data.append(attributes)
                    geometries.append(footprint)
                    stats['success'] += 1
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Fehler bei der Gebäudeverarbeitung: {str(e)}")
                    stats['failed'] += 1
                    continue
                    
            # Erstelle GeoDataFrame
            if not building_data:
                self.logger.warning("⚠️ Keine gültigen Gebäudedaten gefunden")
                return None
                
            gdf = gpd.GeoDataFrame(
                building_data,
                geometry=geometries,
                crs=self.config.geometry_config.get('srs_name', 'EPSG:31256')
            )
            
            # Logge Statistiken
            self._log_statistics(stats)
            
            return gdf
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CityGML-Verarbeitung: {str(e)}")
            return None
            
    def _log_statistics(self, stats: Dict[str, Any]) -> None:
        """Loggt Verarbeitungsstatistiken.
        
        Args:
            stats: Dict[str, Any] - Statistiken
        """
        self.logger.info("\n=== Verarbeitungsstatistiken ===")
        self.logger.info(f"Gesamt: {stats['total']} Gebäude")
        self.logger.info(f"Erfolgreich: {stats['success']} ({stats['success']/stats['total']*100:.1f}%)")
        self.logger.info(f"Fehlgeschlagen: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
        
        self.logger.info("\nGeometrie:")
        geom_stats = stats['geometry']
        self.logger.info(f"Erfolgreich: {geom_stats['success']} ({geom_stats['success']/stats['total']*100:.1f}%)")
        self.logger.info(f"Fehlgeschlagen: {geom_stats['failed']} ({geom_stats['failed']/stats['total']*100:.1f}%)")
        self.logger.info(f"Polygone: {geom_stats['polygons']}")
        self.logger.info(f"MultiPolygone: {geom_stats['multipolygons']}")
        self.logger.info(f"Min. Fläche: {geom_stats['min_area']:.1f} m²")
        self.logger.info(f"Max. Fläche: {geom_stats['max_area']:.1f} m²")
        self.logger.info(f"Durchschn. Fläche: {geom_stats['total_area']/geom_stats['success']:.1f} m²")
        
        self.logger.info("\nAttribute:")
        attr_stats = stats['attributes']
        self.logger.info(f"Erfolgreich: {attr_stats['success']} ({attr_stats['success']/stats['total']*100:.1f}%)")
        self.logger.info(f"Fehlgeschlagen: {attr_stats['failed']} ({attr_stats['failed']/stats['total']*100:.1f}%)")
        
def fetch_citygml_buildings(citygml_file: str, output_dir: str, config: Dict[str, Any]) -> Optional[gpd.GeoDataFrame]:
    """Hilfsfunktion zum Abrufen von CityGML-Gebäudedaten.
    
    Args:
        citygml_file: str - Pfad zur CityGML-Datei
        output_dir: str - Ausgabeverzeichnis
        config: Dict[str, Any] - CityGML-Konfiguration
        
    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame mit Gebäudedaten oder None bei Fehler
    """
    try:
        # Erstelle Fetcher
        fetcher = ViennaCityGMLFetcher(config=config)
        
        # Verarbeite CityGML
        buildings = fetcher.process_citygml(Path(citygml_file))
        if buildings is None:
            return None
            
        # Speichere Ergebnis
        if output_dir:
            output_path = Path(output_dir) / "buildings.gpkg"
            buildings.to_file(output_path, driver="GPKG")
            logging.info(f"✅ Gebäude gespeichert in {output_path}")
            
        return buildings
        
    except Exception as e:
        logging.error(f"❌ Fehler beim Laden der CityGML: {str(e)}")
        return None 
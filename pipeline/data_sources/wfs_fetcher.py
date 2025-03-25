"""
WFS-Fetcher für die Verarbeitung von WFS-Daten aus Wien.
"""

import logging
from typing import Dict, Any, Optional
import geopandas as gpd
from pathlib import Path

from pipeline.data_sources.wfs import (
    WFSBaseClient,
    WFSConfig,
    WFSStreamHandler,
    WFSGeometryProcessor
)

class ViennaWFSFetcher:
    """Fetcher für WFS-Daten aus Wien."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """Initialisiert den Vienna WFS Fetcher.
        
        Args:
            config: Optional[Dict] - Direkte Konfiguration
            config_path: Optional[str] - Pfad zur Konfigurationsdatei
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialisiere Konfiguration
        self.config = WFSConfig(config=config, config_path=config_path)
        
        try:
            # Initialisiere WFS Client nur wenn URL vorhanden
            if self.config.url:
                self.client = WFSBaseClient(
                    url=self.config.url,
                    version=self.config.version,
                    timeout=self.config.timeout,
                    srs_name=self.config.srs_name
                )
                
                # Initialisiere Stream Handler
                self.stream_handler = WFSStreamHandler(
                    client=self.client,
                    streams=self.config.streams
                )
                
                # Initialisiere Geometrie Prozessor
                self.geometry_processor = WFSGeometryProcessor(
                    srs_name=self.config.srs_name
                )
            else:
                self.client = None
                self.stream_handler = None
                self.geometry_processor = None
                self.logger.warning("⚠️ Keine WFS-URL konfiguriert")
                
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der WFS-Initialisierung: {str(e)}")
            self.client = None
            self.stream_handler = None
            self.geometry_processor = None
        
    def fetch_buildings(self, bbox: Optional[str] = None) -> Dict[str, gpd.GeoDataFrame]:
        """Holt Gebäudedaten vom WFS Service.
        
        Args:
            bbox: Optional[str] - Bounding Box für die Abfrage
            
        Returns:
            Dict[str, gpd.GeoDataFrame]: Dictionary mit Stream-Namen und GeoDataFrames
        """
        try:
            if not self.stream_handler:
                self.logger.warning("⚠️ WFS nicht initialisiert")
                return {}
                
            self.logger.info("🔄 Hole Gebäudedaten vom WFS...")
            
            # Verarbeite alle konfigurierten Streams
            results = self.stream_handler.process_streams(bbox)
            
            if not results:
                self.logger.warning("⚠️ Keine Gebäudedaten gefunden")
                return {}
                
            # Validiere Geometrien
            for name, gdf in results.items():
                results[name] = self.geometry_processor.validate_geometry(gdf)
                
            self.logger.info(f"✅ {len(results)} Streams erfolgreich verarbeitet")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen der Gebäudedaten: {str(e)}")
            return {}
            
    def fetch_building_model(self, site_polygon: gpd.GeoDataFrame) -> Dict[str, gpd.GeoDataFrame]:
        """Holt Gebäudemodell-Daten für einen bestimmten Bereich.
        
        Args:
            site_polygon: GeoDataFrame mit Polygon für den Bereich
            
        Returns:
            Dict[str, gpd.GeoDataFrame]: Dictionary mit Stream-Namen und GeoDataFrames
        """
        try:
            if not self.geometry_processor:
                self.logger.warning("⚠️ WFS nicht initialisiert")
                return {}
                
            # Erstelle BBOX aus site_polygon
            bbox = self.geometry_processor.create_bbox_from_gdf(site_polygon)
            if not bbox:
                raise ValueError("❌ Konnte keine BBOX aus site_polygon erstellen")
                
            self.logger.info(f"🔄 Hole Gebäudemodell-Daten für BBOX: {bbox}")
            return self.fetch_buildings(bbox)
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen des Gebäudemodells: {str(e)}")
            return {}
            
def fetch_wfs_buildings(config: Optional[Dict[str, Any]] = None) -> Dict[str, gpd.GeoDataFrame]:
    """Hilfsfunktion zum Abrufen von WFS-Gebäudedaten.
    
    Args:
        config: Optional[Dict] - WFS Konfiguration
        
    Returns:
        Dict[str, gpd.GeoDataFrame]: Dictionary mit Stream-Namen und GeoDataFrames
    """
    try:
        fetcher = ViennaWFSFetcher(config=config)
        return fetcher.fetch_buildings()
    except Exception as e:
        logging.error(f"❌ Fehler beim Abrufen der WFS-Daten: {str(e)}")
        return {}

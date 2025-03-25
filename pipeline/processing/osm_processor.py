"""
OSM-Prozessor für die Verarbeitung von OpenStreetMap-Daten.

Dieser Prozessor implementiert die spezifische Verarbeitung von OSM-Daten
für Gebäude und Straßen.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import logging
from shapely.geometry import Polygon, MultiPolygon, LineString

from pipeline.processing.base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class OSMProcessor(BaseProcessor):
    """Prozessor für OpenStreetMap-Daten."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den OSM-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        
    def process(self, osm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet OSM-Daten.
        
        Args:
            osm_data: Dictionary mit OSM-Daten für Gebäude und Straßen
            
        Returns:
            Verarbeitete OSM-Daten
        """
        try:
            if not self.validate_input(osm_data):
                return {}
                
            # Extrahiere Gebäude und Straßen
            buildings = osm_data.get('buildings', {})
            streets = osm_data.get('streets', {})
            
            # Verarbeite Gebäude
            processed_buildings = self._process_buildings(buildings)
            if not processed_buildings:
                logger.warning("⚠️ Keine Gebäudedaten verarbeitet")
                
            # Verarbeite Straßen
            processed_streets = self._process_streets(streets)
            if not processed_streets:
                logger.warning("⚠️ Keine Straßendaten verarbeitet")
                
            return {
                'buildings': processed_buildings,
                'streets': processed_streets
            }
            
        except Exception as e:
            self.handle_error(e, "osm_processing")
            return {}
            
    def validate_input(self, osm_data: Dict[str, Any]) -> bool:
        """
        Validiert die OSM-Eingabedaten.
        
        Args:
            osm_data: OSM-Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            if not isinstance(osm_data, dict):
                logger.error("❌ OSM-Daten müssen als Dictionary vorliegen")
                return False
                
            # Prüfe Gebäudedaten
            buildings = osm_data.get('buildings')
            if buildings is not None:
                if not isinstance(buildings, (gpd.GeoDataFrame, dict)):
                    logger.error("❌ Gebäudedaten haben falsches Format")
                    return False
                    
            # Prüfe Straßendaten
            streets = osm_data.get('streets')
            if streets is not None:
                if not isinstance(streets, (gpd.GeoDataFrame, dict)):
                    logger.error("❌ Straßendaten haben falsches Format")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Validierung: {str(e)}")
            return False
            
    def _process_buildings(self, buildings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet OSM-Gebäudedaten.
        
        Args:
            buildings: OSM-Gebäudedaten
            
        Returns:
            Verarbeitete Gebäudedaten
        """
        try:
            if not buildings:
                return {}
                
            # Validiere Geometrien
            if not self.validate_geometry(buildings, ['Polygon', 'MultiPolygon']):
                return {}
                
            # Extrahiere relevante Attribute
            processed = buildings.copy()
            
            # Konvertiere MultiPolygons zu einzelnen Polygonen
            if isinstance(processed, gpd.GeoDataFrame):
                processed = processed.explode(index_parts=True)
                
            return {
                'features': processed
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return {}
            
    def _process_streets(self, streets: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet OSM-Straßendaten.
        
        Args:
            streets: OSM-Straßendaten
            
        Returns:
            Verarbeitete Straßendaten
        """
        try:
            if not streets:
                return {}
                
            # Validiere Geometrien
            if not self.validate_geometry(streets, ['LineString', 'MultiLineString']):
                return {}
                
            # Extrahiere relevante Attribute
            processed = streets.copy()
            
            # Konvertiere MultiLineStrings zu einzelnen LineStrings
            if isinstance(processed, gpd.GeoDataFrame):
                processed = processed.explode(index_parts=True)
                
            return {
                'features': processed
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Straßenverarbeitung: {str(e)}")
            return {}
            
    def validate_geometry(self, data: Union[gpd.GeoDataFrame, Dict[str, Any]], allowed_types: List[str]) -> bool:
        """
        Validiert die Geometrien der OSM-Daten.
        
        Args:
            data: OSM-Daten
            allowed_types: Erlaubte Geometrietypen
            
        Returns:
            True wenn Geometrien valide
        """
        try:
            if isinstance(data, gpd.GeoDataFrame):
                if 'geometry' not in data.columns:
                    logger.error("❌ Keine Geometriespalte gefunden")
                    return False
                    
                # Prüfe Geometrietypen
                invalid_types = [t for t in data.geometry.type.unique() if t not in allowed_types]
                if invalid_types:
                    logger.error(f"❌ Ungültige Geometrietypen: {invalid_types}")
                    return False
                    
                # Prüfe auf ungültige Geometrien
                invalid_geoms = data[~data.geometry.is_valid]
                if not invalid_geoms.empty:
                    logger.warning(f"⚠️ {len(invalid_geoms)} ungültige Geometrien gefunden")
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return False 
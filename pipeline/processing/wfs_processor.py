"""
WFS-Prozessor für die Verarbeitung von WFS-Gebäudedaten.

Dieser Prozessor implementiert die spezifische Verarbeitung von WFS-Daten
mit Fokus auf Gebäude und deren Attribute.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import logging
from shapely.geometry import Polygon, MultiPolygon

from pipeline.processing.base_processor import BaseProcessor
from .geometry_processor import GeometryProcessor
from .attribute_processor import AttributeProcessor

logger = logging.getLogger(__name__)

class WFSProcessor(BaseProcessor):
    """Prozessor für WFS-Daten."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den WFS-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        
        # Initialisiere Unterprozessoren
        self.geometry_processor = GeometryProcessor(config)
        self.attribute_processor = AttributeProcessor(config)
        
        # Lade WFS-spezifische Konfiguration
        self.wfs_config = config.get('wfs', {})
        
    def process(self, wfs_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet WFS-Daten.
        
        Args:
            wfs_data: WFS-Gebäudedaten
            
        Returns:
            Verarbeitete Gebäudedaten
        """
        try:
            if not self.validate_input(wfs_data):
                return {}
                
            # Extrahiere und verarbeite Gebäude
            processed_buildings = self._process_buildings(wfs_data)
            if not processed_buildings:
                logger.warning("⚠️ Keine Gebäudedaten verarbeitet")
                return {}
                
            return {
                'buildings': processed_buildings
            }
            
        except Exception as e:
            self.handle_error(e, "wfs_processing")
            return {}
            
    def validate_input(self, wfs_data: Dict[str, Any]) -> bool:
        """
        Validiert die WFS-Eingabedaten.
        
        Args:
            wfs_data: WFS-Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            if not isinstance(wfs_data, (gpd.GeoDataFrame, dict)):
                logger.error("❌ WFS-Daten haben falsches Format")
                return False
                
            if isinstance(wfs_data, gpd.GeoDataFrame):
                if 'geometry' not in wfs_data.columns:
                    logger.error("❌ Keine Geometriespalte gefunden")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Validierung: {str(e)}")
            return False
            
    def _process_buildings(self, buildings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet WFS-Gebäudedaten.
        
        Args:
            buildings: WFS-Gebäudedaten
            
        Returns:
            Verarbeitete Gebäudedaten
        """
        try:
            if isinstance(buildings, gpd.GeoDataFrame) and buildings.empty:
                return {}
                
            # Validiere Geometrien
            if not self.validate_geometry(buildings, ['Polygon', 'MultiPolygon']):
                return {}
                
            # Extrahiere relevante Attribute
            processed = buildings.copy()
            
            # Konvertiere MultiPolygons zu einzelnen Polygonen
            if isinstance(processed, gpd.GeoDataFrame):
                processed = processed.explode(index_parts=True)
                
            # Validiere Attribute
            processed = self._validate_attributes(processed)
                
            return {
                'features': processed
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return {}
            
    def _validate_attributes(self, buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Validiert die Attribute der WFS-Daten.
        
        Args:
            buildings: GeoDataFrame mit Gebäuden
            
        Returns:
            Validierte Gebäude
        """
        try:
            if not isinstance(buildings, gpd.GeoDataFrame):
                return buildings
                
            # Prüfe erforderliche Attribute
            required_fields = ['OBJECTID', 'SHAPE_AREA', 'SHAPE_LEN']
            missing_fields = [field for field in required_fields if field not in buildings.columns]
            
            if missing_fields:
                logger.warning(f"⚠️ Fehlende Pflichtfelder: {missing_fields}")
                
            return buildings
            
        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der Attributvalidierung: {str(e)}")
            return buildings
            
    def validate_geometry(self, data: Union[gpd.GeoDataFrame, Dict[str, Any]], allowed_types: List[str]) -> bool:
        """
        Validiert die Geometrien der WFS-Daten.
        
        Args:
            data: WFS-Daten
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
            
    def _extract_features(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert Features aus WFS-Daten.
        
        Args:
            data: WFS-Rohdaten
            
        Returns:
            Extrahierte Features
        """
        try:
            # Konvertiere zu GeoDataFrame wenn nötig
            if isinstance(data, dict):
                gdf = gpd.GeoDataFrame([data])
            elif isinstance(data, gpd.GeoDataFrame):
                gdf = data
            else:
                self.logger.error("❌ Ungültiges Eingabeformat")
                return {}
                
            # Extrahiere Features
            features = gdf.copy()
            
            # Protokolliere Statistiken
            self.logger.info(f"📊 Gefundene Features: {len(features)}")
            
            # Füge Metadaten hinzu
            features['source'] = 'wfs'
            features['is_wfs'] = True
            
            return {
                'features': features
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Feature-Extraktion: {str(e)}")
            return {}
            
    def validate_wfs_data(self, data: Dict[str, Any]) -> bool:
        """
        Validiert WFS-spezifische Daten.
        
        Args:
            data: Zu validierende WFS-Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            # Prüfe grundlegende Struktur
            if not isinstance(data, dict):
                self.logger.error("❌ Daten müssen als Dictionary vorliegen")
                return False
                
            # Prüfe erforderliche Schlüssel
            required_keys = ['geometry', 'properties']
            missing_keys = [key for key in required_keys if key not in data]
            
            if missing_keys:
                self.logger.error(f"❌ Fehlende Pflichtfelder: {missing_keys}")
                return False
                
            # Prüfe Geometrietyp
            geom = data.get('geometry')
            if not isinstance(geom, (Polygon, MultiPolygon)):
                self.logger.error("❌ Ungültiger Geometrietyp")
                return False
                
            # Prüfe Properties
            properties = data.get('properties', {})
            required_properties = self.wfs_config.get('required_properties', [])
            missing_properties = [prop for prop in required_properties if prop not in properties]
            
            if missing_properties:
                self.logger.warning(f"⚠️ Fehlende Properties: {missing_properties}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der WFS-Validierung: {str(e)}")
            return False
            
    def _process_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet WFS-Properties.
        
        Args:
            properties: WFS-Properties
            
        Returns:
            Verarbeitete Properties
        """
        try:
            # Hole Property-Mapping aus Konfiguration
            property_mapping = self.wfs_config.get('property_mapping', {})
            
            # Wende Mapping an
            mapped_properties = {}
            for target_field, source_field in property_mapping.items():
                if source_field in properties:
                    mapped_properties[target_field] = properties[source_field]
                    
            return mapped_properties
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Property-Verarbeitung: {str(e)}")
            return properties
            
    def _validate_stream(self, stream_name: str, data: Dict[str, Any]) -> bool:
        """
        Validiert einen WFS-Stream.
        
        Args:
            stream_name: Name des Streams
            data: Stream-Daten
            
        Returns:
            True wenn Stream valide
        """
        try:
            # Hole Stream-Konfiguration
            stream_config = self.wfs_config.get('streams', {}).get(stream_name, {})
            if not stream_config:
                self.logger.warning(f"⚠️ Keine Konfiguration für Stream '{stream_name}' gefunden")
                return False
                
            # Prüfe erforderliche Felder
            required_fields = stream_config.get('required_fields', [])
            if not all(field in data for field in required_fields):
                self.logger.error(f"❌ Fehlende Pflichtfelder in Stream '{stream_name}'")
                return False
                
            # Prüfe Geometrietyp
            allowed_types = stream_config.get('geometry_types', ['Polygon', 'MultiPolygon'])
            if data.get('geometry', {}).get('type') not in allowed_types:
                self.logger.error(f"❌ Ungültiger Geometrietyp in Stream '{stream_name}'")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Stream-Validierung: {str(e)}")
            return False 
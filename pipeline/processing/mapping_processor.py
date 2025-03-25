"""
Zentraler Mapping-Prozessor für die einheitliche Transformation von Gebäudedaten.

Dieser Prozessor implementiert das zentrale Mapping aller Quelldaten in ein
einheitliches Zielschema gemäß den definierten Transformationsregeln.
"""

from typing import Dict, Any, Optional, List, Union
import geopandas as gpd
import pandas as pd
import logging
import yaml
from pathlib import Path
from shapely.geometry import Polygon, MultiPolygon

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class MappingProcessor(BaseProcessor):
    """Prozessor für zentrales Daten-Mapping."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Mapping-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        
        # Lade Mapping-Konfiguration
        self.mapping_config = self._load_mapping_config()
        
    def _load_mapping_config(self) -> Dict[str, Any]:
        """
        Lädt die Mapping-Konfiguration aus der YAML-Datei.
        
        Returns:
            Mapping-Konfiguration
        """
        try:
            mapping_path = Path(self.config.get('mapping', {}).get('config_file', 'config/mapping.yml'))
            
            if not mapping_path.exists():
                self.logger.error(f"❌ Mapping-Konfiguration nicht gefunden: {mapping_path}")
                return {}
                
            with open(mapping_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Mapping-Konfiguration: {str(e)}")
            return {}
            
    def process(self, data: Dict[str, Any], source_type: str) -> Dict[str, Any]:
        """
        Verarbeitet Daten gemäß dem konfigurierten Mapping.
        
        Args:
            data: Quelldaten
            source_type: Typ der Datenquelle (citygml, wfs, osm)
            
        Returns:
            Gemappte Daten
        """
        try:
            if not self.validate_data(data):
                return {}
                
            # Hole Mapping für den Quelltyp
            mapping = self.mapping_config.get('mappings', {}).get('building', {}).get(source_type, {})
            if not mapping:
                self.logger.error(f"❌ Kein Mapping für Quelltyp '{source_type}' gefunden")
                return {}
                
            # Wende Mapping an
            mapped_data = self._apply_mapping(data, mapping)
            if not mapped_data:
                return {}
                
            # Validiere transformierte Daten
            if not self._validate_mapped_data(mapped_data):
                return {}
                
            return mapped_data
            
        except Exception as e:
            self.handle_error(e, "mapping_processing")
            return {}
            
    def _apply_mapping(self, data: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Wendet das konfigurierte Mapping auf die Daten an.
        
        Args:
            data: Quelldaten
            mapping: Mapping-Konfiguration
            
        Returns:
            Gemappte Daten
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
                
            # Erstelle neuen DataFrame für gemappte Daten
            mapped_gdf = gpd.GeoDataFrame(geometry=gdf.geometry)
            
            # Wende Attribut-Mapping an
            for target_field, source_field in mapping.items():
                if source_field in gdf.columns:
                    mapped_gdf[target_field] = gdf[source_field]
                else:
                    self.logger.warning(f"⚠️ Quellfeld '{source_field}' nicht gefunden")
                    
            # Übernehme Metadaten
            mapped_gdf['source'] = gdf.get('source', 'unknown')
            mapped_gdf['original_id'] = gdf.index
            
            return {
                'features': mapped_gdf
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Mapping: {str(e)}")
            return {}
            
    def _validate_mapped_data(self, data: Dict[str, Any]) -> bool:
        """
        Validiert die gemappten Daten gegen das Zielschema.
        
        Args:
            data: Gemappte Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            if not isinstance(data, dict) or 'features' not in data:
                self.logger.error("❌ Ungültiges Datenformat")
                return False
                
            features = data['features']
            if not isinstance(features, gpd.GeoDataFrame):
                self.logger.error("❌ Features müssen als GeoDataFrame vorliegen")
                return False
                
            # Prüfe erforderliche Felder
            required_fields = self.config.get('mapping', {}).get('required_fields', [])
            missing_fields = [field for field in required_fields if field not in features.columns]
            
            if missing_fields:
                self.logger.error(f"❌ Fehlende Pflichtfelder nach Mapping: {missing_fields}")
                return False
                
            # Prüfe Geometrien
            invalid_geoms = ~features.geometry.is_valid
            if invalid_geoms.any():
                self.logger.warning(f"⚠️ {invalid_geoms.sum()} ungültige Geometrien gefunden")
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Validierung: {str(e)}")
            return False
            
    def transform_geometry(self, geometry: Union[Polygon, MultiPolygon]) -> Optional[Union[Polygon, MultiPolygon]]:
        """
        Transformiert eine Geometrie gemäß den Transformationsregeln.
        
        Args:
            geometry: Zu transformierende Geometrie
            
        Returns:
            Transformierte Geometrie
        """
        try:
            if not geometry.is_valid:
                geometry = geometry.buffer(0)
                
            if not geometry.is_valid:
                self.logger.error("❌ Geometrie konnte nicht repariert werden")
                return None
                
            return geometry
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrie-Transformation: {str(e)}")
            return None 
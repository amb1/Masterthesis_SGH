"""
Attribut-Prozessor für die Transformation von Attributen.

Dieser Prozessor implementiert die Transformation und Validierung von Attributen.
"""

from typing import Dict, Any, List, Optional, Union
import pandas as pd
import numpy as np
import logging
from datetime import datetime

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)

class AttributeProcessor(BaseProcessor):
    """Prozessor für Attribut-Transformationen."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den Attribut-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        self.mapping_config = config.get('mapping', {})
        self.validation_config = config.get('validation', {})
        
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet die Attribute.
        
        Args:
            data: Eingabedaten mit Attributen
            
        Returns:
            Verarbeitete Daten
        """
        try:
            if not self.validate_data(data):
                return {}
                
            # Konvertiere zu DataFrame wenn nötig
            if isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, pd.DataFrame):
                df = data
            else:
                self.logger.error("❌ Ungültiges Eingabeformat")
                return {}
                
            # Validiere Attribute
            df = self.validate_attributes(df)
            
            # Transformiere Attribute
            df = self.transform_attributes(df)
            
            # Berechne abgeleitete Attribute
            df = self.calculate_derived_attributes(df)
            
            return df.to_dict('records')[0] if len(df) == 1 else df.to_dict('records')
            
        except Exception as e:
            self.handle_error(e, "attribute_processing")
            return {}
            
    def validate_attributes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Validiert die Attribute.
        
        Args:
            df: Eingabe-DataFrame
            
        Returns:
            Validierter DataFrame
        """
        try:
            # Prüfe Pflichtfelder
            required_fields = self.validation_config.get('required_fields', [])
            missing_fields = [field for field in required_fields if field not in df.columns]
            
            if missing_fields:
                self.logger.warning(f"⚠️ Fehlende Pflichtfelder: {missing_fields}")
                
            # Prüfe Datentypen
            field_types = self.validation_config.get('field_types', {})
            for field, expected_type in field_types.items():
                if field in df.columns:
                    try:
                        df[field] = df[field].astype(expected_type)
                    except Exception as e:
                        self.logger.warning(f"⚠️ Fehler bei Typkonvertierung für {field}: {str(e)}")
                        
            # Prüfe Wertebereiche
            value_ranges = self.validation_config.get('value_ranges', {})
            for field, range_config in value_ranges.items():
                if field in df.columns:
                    min_val = range_config.get('min')
                    max_val = range_config.get('max')
                    
                    if min_val is not None:
                        invalid_min = df[df[field] < min_val]
                        if not invalid_min.empty:
                            self.logger.warning(f"⚠️ {len(invalid_min)} Werte unter Minimum in {field}")
                            
                    if max_val is not None:
                        invalid_max = df[df[field] > max_val]
                        if not invalid_max.empty:
                            self.logger.warning(f"⚠️ {len(invalid_max)} Werte über Maximum in {field}")
                            
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Attributvalidierung: {str(e)}")
            return df
            
    def transform_attributes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transformiert die Attribute.
        
        Args:
            df: Eingabe-DataFrame
            
        Returns:
            Transformierter DataFrame
        """
        try:
            # Wende Mapping-Regeln an
            field_mappings = self.mapping_config.get('field_mappings', {})
            for target_field, mapping_config in field_mappings.items():
                source_field = mapping_config.get('source_field')
                mapping_dict = mapping_config.get('mapping', {})
                
                if source_field in df.columns:
                    df[target_field] = df[source_field].map(mapping_dict)
                    
            # Wende Formatierungsregeln an
            formatting = self.mapping_config.get('formatting', {})
            for field, format_config in formatting.items():
                if field in df.columns:
                    format_type = format_config.get('type')
                    format_pattern = format_config.get('pattern')
                    
                    if format_type == 'date':
                        df[field] = pd.to_datetime(df[field], format=format_pattern)
                    elif format_type == 'number':
                        df[field] = df[field].apply(lambda x: format_pattern.format(x))
                        
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Attributtransformation: {str(e)}")
            return df
            
    def calculate_derived_attributes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Berechnet abgeleitete Attribute.
        
        Args:
            df: Eingabe-DataFrame
            
        Returns:
            DataFrame mit zusätzlichen Attributen
        """
        try:
            # Berechne neue Attribute basierend auf Konfiguration
            derived_fields = self.mapping_config.get('derived_fields', {})
            
            for new_field, calc_config in derived_fields.items():
                operation = calc_config.get('operation')
                source_fields = calc_config.get('source_fields', [])
                
                if all(field in df.columns for field in source_fields):
                    if operation == 'sum':
                        df[new_field] = df[source_fields].sum(axis=1)
                    elif operation == 'mean':
                        df[new_field] = df[source_fields].mean(axis=1)
                    elif operation == 'max':
                        df[new_field] = df[source_fields].max(axis=1)
                    elif operation == 'min':
                        df[new_field] = df[source_fields].min(axis=1)
                        
            return df
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Berechnung abgeleiteter Attribute: {str(e)}")
            return df
            
    def map_value(self, value: Any, mapping_dict: Dict[str, Any], default: Any = None) -> Any:
        """
        Mappt einen Wert anhand eines Mapping-Dictionaries.
        
        Args:
            value: Zu mappender Wert
            mapping_dict: Mapping-Dictionary
            default: Standardwert wenn keine Zuordnung gefunden
            
        Returns:
            Gemappter Wert
        """
        try:
            if value in mapping_dict:
                return mapping_dict[value]
            return default
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Mapping von {value}: {str(e)}")
            return default
            
    def convert_type(self, value: Any, target_type: str) -> Any:
        """
        Konvertiert einen Wert in den Zieltyp.
        
        Args:
            value: Zu konvertierender Wert
            target_type: Zieldatentyp
            
        Returns:
            Konvertierter Wert
        """
        try:
            if target_type == 'int':
                return int(float(value))
            elif target_type == 'float':
                return float(value)
            elif target_type == 'str':
                return str(value)
            elif target_type == 'bool':
                return bool(value)
            elif target_type == 'date':
                return pd.to_datetime(value)
            else:
                return value
                
        except Exception as e:
            self.logger.error(f"❌ Fehler bei Typkonvertierung zu {target_type}: {str(e)}")
            return value 
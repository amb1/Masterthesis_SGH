import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Klasse für die Fehlerbehandlung"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den ErrorHandler
        
        Args:
            config (Dict[str, Any]): Konfigurationsdictionary
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def handle_missing_fields(self, data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Behandelt fehlende Felder mit Standardwerten
        
        Args:
            data (Dict[str, Any]): Gebäudedaten
            required_fields (List[str]): Liste der erforderlichen Felder
            
        Returns:
            Dict[str, Any]: Verarbeitete Daten
        """
        try:
            defaults = self.config.get('defaults', {})
            for field in required_fields:
                if field not in data:
                    default_value = defaults.get(field, self.get_default_value(field))
                    data[field] = default_value
                    self.logger.warning(f"⚠️ Standardwert für {field}: {default_value}")
            return data
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Behandlung fehlender Felder: {str(e)}")
            return data
            
    def handle_invalid_geometry(self, geometry: Any) -> Optional[Any]:
        """Behandelt ungültige Geometrien
        
        Args:
            geometry (Any): Geometrieobjekt
            
        Returns:
            Optional[Any]: Korrigierte Geometrie oder None
        """
        try:
            if not hasattr(geometry, 'is_valid'):
                self.logger.error("❌ Ungültiges Geometrieformat")
                return None
                
            if not geometry.is_valid:
                # Versuche die Geometrie zu korrigieren
                try:
                    corrected = geometry.buffer(0)
                    if corrected.is_valid:
                        self.logger.warning("⚠️ Geometrie wurde korrigiert")
                        return corrected
                    else:
                        self.logger.error("❌ Geometrie konnte nicht korrigiert werden")
                        return None
                except Exception as e:
                    self.logger.error(f"❌ Fehler bei der Geometriekorrektur: {str(e)}")
                    return None
                    
            return geometry
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometriebehandlung: {str(e)}")
            return None
            
    def handle_invalid_data_types(self, data: Dict[str, Any], type_mapping: Dict[str, type]) -> Dict[str, Any]:
        """Behandelt ungültige Datentypen
        
        Args:
            data (Dict[str, Any]): Gebäudedaten
            type_mapping (Dict[str, type]): Mapping von Feldern zu Datentypen
            
        Returns:
            Dict[str, Any]: Verarbeitete Daten
        """
        try:
            for field, expected_type in type_mapping.items():
                if field in data:
                    try:
                        data[field] = expected_type(data[field])
                    except (ValueError, TypeError):
                        default_value = self.get_default_value(field)
                        data[field] = default_value
                        self.logger.warning(f"⚠️ Ungültiger Datentyp für {field}, Standardwert verwendet: {default_value}")
            return data
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Datentypbehandlung: {str(e)}")
            return data
            
    def get_default_value(self, field: str) -> Any:
        """Gibt den Standardwert für ein Feld zurück
        
        Args:
            field (str): Feldname
            
        Returns:
            Any: Standardwert
        """
        try:
            defaults = self.config.get('defaults', {})
            if field in defaults:
                return defaults[field]
                
            # Standardwerte basierend auf Feldtyp
            if field in ['floors_ag', 'floors_bg', 'YEAR']:
                return 0
            elif field in ['height_ag', 'height_bg', 'USE1_R', 'USE2_R', 'USE3_R']:
                return 0.0
            elif field in ['Name', 'REFERENCE', 'house_no', 'street', 'postcode', 
                         'house_name', 'resi_type', 'city', 'country', 'STANDARD', 
                         'USE1', 'USE2', 'USE3']:
                return ""
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Abrufen des Standardwerts für {field}: {str(e)}")
            return None 
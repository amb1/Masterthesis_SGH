import logging
from typing import Dict, Any, List, Optional
import geopandas as gpd
import pandas as pd
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

class CEAFileCreator:
    """Klasse für die Erstellung von CEA-Dateien"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den CEAFileCreator
        
        Args:
            config (Dict[str, Any]): Konfigurationsdictionary
        """
        self.config = config
        self.field_mappings = self._load_field_mappings()
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _load_field_mappings(self) -> Dict[str, str]:
        """Lädt die Feldzuordnungen aus der Konfiguration"""
        try:
            return self.config.get('cea', {}).get('mapping', {})
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Feldzuordnungen: {str(e)}")
            return {}
            
    def create_zone_shp(self, data: List[Dict[str, Any]], output_path: Path) -> bool:
        """Erstellt die zone.shp Datei
        
        Args:
            data (List[Dict[str, Any]]): Liste der Gebäudedaten
            output_path (Path): Ausgabepfad für die zone.shp
            
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Erstelle GeoDataFrame
            gdf = gpd.GeoDataFrame(data)
            
            # Validiere Felder
            if not self._validate_zone_shp(gdf):
                return False
                
            # Speichere Shapefile
            gdf.to_file(output_path)
            self.logger.info(f"✅ zone.shp erstellt: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen der zone.shp: {str(e)}")
            return False
            
    def create_typology_dbf(self, data: List[Dict[str, Any]], output_path: Path) -> bool:
        """Erstellt die typology.dbf Datei
        
        Args:
            data (List[Dict[str, Any]]): Liste der Gebäudetypologien
            output_path (Path): Ausgabepfad für die typology.dbf
            
        Returns:
            bool: True wenn erfolgreich, False sonst
        """
        try:
            # Erstelle DataFrame
            df = pd.DataFrame(data)
            
            # Validiere Felder
            if not self._validate_typology_dbf(df):
                return False
                
            # Speichere DBF
            df.to_file(output_path, driver='ESRI Shapefile')
            self.logger.info(f"✅ typology.dbf erstellt: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen der typology.dbf: {str(e)}")
            return False
            
    def _validate_zone_shp(self, gdf: gpd.GeoDataFrame) -> bool:
        """Validiert die Felder der zone.shp"""
        try:
            required_fields = self.config.get('cea', {}).get('fields', {}).get('zone_shp', {}).get('fields', {}).keys()
            
            # Überprüfe erforderliche Felder
            missing_fields = [field for field in required_fields if field not in gdf.columns]
            if missing_fields:
                self.logger.error(f"❌ Fehlende Felder in zone.shp: {missing_fields}")
                return False
                
            # Überprüfe Geometrie
            if not gdf.geometry.is_valid.all():
                self.logger.error("❌ Ungültige Geometrien in zone.shp")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der zone.shp Validierung: {str(e)}")
            return False
            
    def _validate_typology_dbf(self, df: pd.DataFrame) -> bool:
        """Validiert die Felder der typology.dbf"""
        try:
            required_fields = self.config.get('cea', {}).get('fields', {}).get('typology_dbf', {}).get('fields', {}).keys()
            
            # Überprüfe erforderliche Felder
            missing_fields = [field for field in required_fields if field not in df.columns]
            if missing_fields:
                self.logger.error(f"❌ Fehlende Felder in typology.dbf: {missing_fields}")
                return False
                
            # Überprüfe Datentypen
            type_mapping = {
                'YEAR': int,
                'USE1_R': float,
                'USE2_R': float,
                'USE3_R': float
            }
            
            for field, expected_type in type_mapping.items():
                if field in df.columns:
                    try:
                        df[field].astype(expected_type)
                    except (ValueError, TypeError):
                        self.logger.error(f"❌ Ungültiger Datentyp für {field}")
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der typology.dbf Validierung: {str(e)}")
            return False 
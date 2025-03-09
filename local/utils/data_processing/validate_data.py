import logging
import geopandas as gpd
from typing import List, Dict, Any, Optional
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

def validate_geometry(gdf: gpd.GeoDataFrame, required_types: List[str]) -> bool:
    """
    Validiert die Geometrie eines GeoDataFrames
    
    Args:
        gdf: GeoDataFrame zu validieren
        required_types: Liste der erlaubten Geometrietypen
        
    Returns:
        bool: True wenn die Validierung erfolgreich war
    """
    try:
        if gdf is None or gdf.empty:
            logger.error("❌ GeoDataFrame ist leer")
            return False
            
        if 'geometry' not in gdf.columns:
            logger.error("❌ Keine Geometriespalte gefunden")
            return False
            
        # Prüfe Geometrietypen
        geometry_types = gdf.geometry.type.unique()
        invalid_types = [t for t in geometry_types if t not in required_types]
        
        if invalid_types:
            logger.error(f"❌ Ungültige Geometrietypen gefunden: {invalid_types}")
            return False
            
        # Prüfe auf ungültige Geometrien
        invalid_geometries = gdf[~gdf.geometry.is_valid]
        if not invalid_geometries.empty:
            logger.error(f"❌ {len(invalid_geometries)} ungültige Geometrien gefunden")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
        return False

def validate_fields(gdf: gpd.GeoDataFrame, required_fields: List[str]) -> bool:
    """
    Validiert die Felder eines GeoDataFrames
    
    Args:
        gdf: GeoDataFrame zu validieren
        required_fields: Liste der erforderlichen Felder
        
    Returns:
        bool: True wenn die Validierung erfolgreich war
    """
    try:
        if gdf is None or gdf.empty:
            logger.error("❌ GeoDataFrame ist leer")
            return False
            
        # Prüfe erforderliche Felder
        missing_fields = [field for field in required_fields if field not in gdf.columns]
        if missing_fields:
            logger.error(f"❌ Fehlende Felder: {missing_fields}")
            return False
            
        # Prüfe auf NULL-Werte in erforderlichen Feldern
        for field in required_fields:
            null_count = gdf[field].isnull().sum()
            if null_count > 0:
                logger.warning(f"⚠️ {null_count} NULL-Werte im Feld {field}")
                
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Feldvalidierung: {str(e)}")
        return False

def validate_crs(gdf: gpd.GeoDataFrame, required_crs: str) -> bool:
    """
    Validiert das Koordinatenreferenzsystem
    
    Args:
        gdf: GeoDataFrame zu validieren
        required_crs: Erforderliches CRS
        
    Returns:
        bool: True wenn die Validierung erfolgreich war
    """
    try:
        if gdf is None or gdf.empty:
            logger.error("❌ GeoDataFrame ist leer")
            return False
            
        if gdf.crs is None:
            logger.error("❌ Kein CRS definiert")
            return False
            
        if str(gdf.crs) != required_crs:
            logger.error(f"❌ Falsches CRS: {gdf.crs} (erwartet: {required_crs})")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der CRS-Validierung: {str(e)}")
        return False

def validate_data(gdf: gpd.GeoDataFrame, 
                 config: Dict[str, Any],
                 data_type: str) -> bool:
    """
    Führt eine umfassende Validierung der Daten durch
    
    Args:
        gdf: GeoDataFrame zu validieren
        config: Validierungskonfiguration
        data_type: Typ der Daten (z.B. "buildings", "energy")
        
    Returns:
        bool: True wenn die Validierung erfolgreich war
    """
    try:
        if gdf is None or gdf.empty:
            logger.error("❌ GeoDataFrame ist leer")
            return False
            
        # Validiere Geometrie
        if not validate_geometry(gdf, config['validation']['geometry_types']):
            return False
            
        # Validiere Felder
        required_fields = config['validation']['required_fields']
        if data_type in config['merge_fields']:
            required_fields.extend(config['merge_fields'][data_type])
            
        if not validate_fields(gdf, required_fields):
            return False
            
        # Validiere CRS
        if not validate_crs(gdf, config['validation']['crs']):
            return False
            
        logger.info(f"✅ Validierung erfolgreich für {data_type}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Datenvalidierung: {str(e)}")
        return False

class DataValidator:
    """Klasse für die Validierung von Gebäudedaten"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiert den DataValidator
        
        Args:
            config (Dict[str, Any]): Konfigurationsdictionary
        """
        self.config = config
        self.required_fields = self._load_required_fields()
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def _load_required_fields(self) -> Dict[str, List[str]]:
        """Lädt die erforderlichen Felder aus der Konfiguration"""
        try:
            cea_fields = self.config.get('cea', {}).get('fields', {})
            return {
                'zone.shp': cea_fields.get('zone_shp', {}).get('fields', {}).keys(),
                'typology.dbf': cea_fields.get('typology_dbf', {}).get('fields', {}).keys()
            }
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der erforderlichen Felder: {str(e)}")
            return {}
            
    def validate_building(self, building_data: Dict[str, Any]) -> bool:
        """Validiert ein einzelnes Gebäude
        
        Args:
            building_data (Dict[str, Any]): Gebäudedaten
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            # Überprüfe erforderliche Felder
            for field in self.required_fields['zone.shp']:
                if field not in building_data:
                    self.logger.warning(f"⚠️ Fehlendes Feld in Gebäude: {field}")
                    return False
                    
            # Validiere Datentypen
            if not self._validate_data_types(building_data):
                return False
                
            # Validiere Geometrie
            if not self._validate_geometry(building_data):
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Gebäudevalidierung: {str(e)}")
            return False
            
    def _validate_data_types(self, building_data: Dict[str, Any]) -> bool:
        """Überprüft die Datentypen der Felder"""
        try:
            type_mapping = {
                'floors_ag': int,
                'floors_bg': int,
                'height_ag': float,
                'height_bg': float,
                'YEAR': int,
                'USE1_R': float,
                'USE2_R': float,
                'USE3_R': float
            }
            
            for field, expected_type in type_mapping.items():
                if field in building_data:
                    try:
                        expected_type(building_data[field])
                    except (ValueError, TypeError):
                        self.logger.warning(f"⚠️ Ungültiger Datentyp für {field}")
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Datentypvalidierung: {str(e)}")
            return False
            
    def _validate_geometry(self, building_data: Dict[str, Any]) -> bool:
        """Überprüft die Geometrie des Gebäudes"""
        try:
            if 'geometry' not in building_data:
                self.logger.warning("⚠️ Keine Geometrie vorhanden")
                return False
                
            geometry = building_data['geometry']
            if not hasattr(geometry, 'is_valid'):
                self.logger.warning("⚠️ Ungültiges Geometrieformat")
                return False
                
            if not geometry.is_valid:
                self.logger.warning("⚠️ Ungültige Geometrie")
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Geometrievalidierung: {str(e)}")
            return False
            
    def validate_zone_shp(self, zone_gdf: gpd.GeoDataFrame) -> bool:
        """Validiert die zone.shp Datei
        
        Args:
            zone_gdf (gpd.GeoDataFrame): GeoDataFrame mit den Gebäuden
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            # Überprüfe erforderliche Spalten
            required_columns = self.required_fields['zone.shp']
            missing_columns = [col for col in required_columns if col not in zone_gdf.columns]
            
            if missing_columns:
                self.logger.error(f"❌ Fehlende Spalten in zone.shp: {missing_columns}")
                return False
                
            # Validiere jedes Gebäude
            for idx, row in zone_gdf.iterrows():
                building_data = row.to_dict()
                if not self.validate_building(building_data):
                    self.logger.error(f"❌ Ungültiges Gebäude in Zeile {idx}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der zone.shp Validierung: {str(e)}")
            return False
            
    def validate_typology_dbf(self, typology_df: pd.DataFrame) -> bool:
        """Validiert die typology.dbf Datei
        
        Args:
            typology_df (pd.DataFrame): DataFrame mit den Gebäudetypologien
            
        Returns:
            bool: True wenn gültig, False sonst
        """
        try:
            # Überprüfe erforderliche Spalten
            required_columns = self.required_fields['typology.dbf']
            missing_columns = [col for col in required_columns if col not in typology_df.columns]
            
            if missing_columns:
                self.logger.error(f"❌ Fehlende Spalten in typology.dbf: {missing_columns}")
                return False
                
            # Validiere Datentypen
            for idx, row in typology_df.iterrows():
                building_data = row.to_dict()
                if not self._validate_data_types(building_data):
                    self.logger.error(f"❌ Ungültige Daten in Zeile {idx}")
                    return False
                    
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der typology.dbf Validierung: {str(e)}")
            return False 
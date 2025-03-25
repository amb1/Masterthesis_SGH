"""
CityGML-Prozessor für die Verarbeitung von CityGML-Gebäudedaten.

Dieser Prozessor implementiert die spezifische Verarbeitung von CityGML-Daten
mit Fokus auf Gebäude und deren Geometrien.
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
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor

logger = logging.getLogger(__name__)

class CityGMLProcessor(BaseProcessor):
    """Prozessor für CityGML-Daten."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialisiert den CityGML-Prozessor.
        
        Args:
            config: Konfigurationsobjekt
        """
        super().__init__(config)
        
        # Initialisiere Unterprozessoren
        self.geometry_processor = GeometryProcessor(config)
        self.attribute_processor = AttributeProcessor(config)
        
        # Lade CityGML-spezifische Konfiguration
        self.citygml_config = config.get('citygml', {})
        
        self.building_processor = CityGMLBuildingProcessor(config)
        
    def process(self, citygml_path: str) -> gpd.GeoDataFrame:
        """
        Verarbeitet CityGML-Daten und gibt ein GeoDataFrame zurück.
        
        Args:
            citygml_path: Pfad zur CityGML-Datei
            
        Returns:
            GeoDataFrame mit verarbeiteten Gebäudedaten
        """
        return self.building_processor.process_citygml(citygml_path)
            
    def validate_input(self, citygml_data: Dict[str, Any]) -> bool:
        """
        Validiert die CityGML-Eingabedaten.
        
        Args:
            citygml_data: CityGML-Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            if not isinstance(citygml_data, (gpd.GeoDataFrame, dict)):
                logger.error("❌ CityGML-Daten haben falsches Format")
                return False
                
            if isinstance(citygml_data, gpd.GeoDataFrame):
                if 'geometry' not in citygml_data.columns:
                    logger.error("❌ Keine Geometriespalte gefunden")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Validierung: {str(e)}")
            return False
            
    def _process_buildings(self, buildings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verarbeitet CityGML-Gebäudedaten.
        
        Args:
            buildings: CityGML-Gebäudedaten
            
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
                
            # Validiere Gebäudeteile
            processed = self._validate_building_parts(processed)
                
            return {
                'features': processed
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler bei der Gebäudeverarbeitung: {str(e)}")
            return {}
            
    def _validate_building_parts(self, buildings: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Validiert und verarbeitet Gebäudeteile.
        
        Args:
            buildings: GeoDataFrame mit Gebäuden
            
        Returns:
            Verarbeitete Gebäude
        """
        try:
            if not isinstance(buildings, gpd.GeoDataFrame):
                return buildings
                
            # Prüfe auf Gebäudeteile
            if 'building_part' in buildings.columns:
                # Gruppiere nach Haupt- und Nebengebäuden
                main_buildings = buildings[buildings['building_part'].isna()]
                building_parts = buildings[buildings['building_part'].notna()]
                
                if not building_parts.empty:
                    logger.info(f"ℹ️ {len(building_parts)} Gebäudeteile gefunden")
                    
            return buildings
            
        except Exception as e:
            logger.warning(f"⚠️ Fehler bei der Validierung von Gebäudeteilen: {str(e)}")
            return buildings
            
    def validate_geometry(self, data: Union[gpd.GeoDataFrame, Dict[str, Any]], allowed_types: List[str]) -> bool:
        """
        Validiert die Geometrien der CityGML-Daten.
        
        Args:
            data: CityGML-Daten
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
            
    def _extract_buildings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahiert Gebäude aus CityGML-Daten.
        
        Args:
            data: CityGML-Rohdaten
            
        Returns:
            Extrahierte Gebäudedaten
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
                
            # Extrahiere Gebäude
            buildings = gdf[~gdf['is_building_part']].copy()
            building_parts = gdf[gdf['is_building_part']].copy()
            
            # Protokolliere Statistiken
            self.logger.info(f"📊 Gefundene Gebäude: {len(buildings)}")
            self.logger.info(f"📊 Gefundene Gebäudeteile: {len(building_parts)}")
            
            # Füge Metadaten hinzu
            buildings['source'] = 'citygml'
            building_parts['source'] = 'citygml'
            
            return {
                'buildings': buildings,
                'building_parts': building_parts
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der Gebäudeextraktion: {str(e)}")
            return {}
            
    def _combine_building_parts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Kombiniert Gebäudeteile mit ihren Hauptgebäuden.
        
        Args:
            data: Gebäudedaten mit Hauptgebäuden und Teilen
            
        Returns:
            Kombinierte Gebäudedaten
        """
        try:
            buildings = data.get('buildings', pd.DataFrame())
            building_parts = data.get('building_parts', pd.DataFrame())
            
            if building_parts.empty:
                return data
                
            # Gruppiere Gebäudeteile nach Parent-ID
            grouped_parts = building_parts.groupby('parent_id')
            
            # Verarbeite jede Gruppe
            for parent_id, parts in grouped_parts:
                if parent_id in buildings.index:
                    # Hole Hauptgebäude
                    main_building = buildings.loc[parent_id]
                    
                    # Kombiniere Geometrien
                    all_geometries = [main_building.geometry] + list(parts.geometry)
                    combined_geom = MultiPolygon(all_geometries)
                    
                    # Aktualisiere Hauptgebäude
                    buildings.at[parent_id, 'geometry'] = combined_geom
                    buildings.at[parent_id, 'has_building_parts'] = True
                    buildings.at[parent_id, 'building_parts_count'] = len(parts)
                    
                    # Übernehme Attribute von Gebäudeteilen
                    for attr in parts.columns:
                        if attr not in ['geometry', 'gml_id', 'parent_id', 'type']:
                            values = parts[attr].dropna()
                            if not values.empty:
                                buildings.at[parent_id, f'part_{attr}'] = values.iloc[0]
                                
            self.logger.info(f"✅ {len(grouped_parts)} Gebäudeteile verarbeitet")
            
            return {
                'buildings': buildings,
                'building_parts': building_parts
            }
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Kombinieren der Gebäudeteile: {str(e)}")
            return data
            
    def validate_citygml_data(self, data: Dict[str, Any]) -> bool:
        """
        Validiert CityGML-spezifische Daten.
        
        Args:
            data: Zu validierende CityGML-Daten
            
        Returns:
            True wenn Daten valide
        """
        try:
            # Prüfe grundlegende Struktur
            if not isinstance(data, dict):
                self.logger.error("❌ Daten müssen als Dictionary vorliegen")
                return False
                
            # Prüfe erforderliche Schlüssel
            required_keys = ['gml_id', 'geometry', 'type']
            missing_keys = [key for key in required_keys if key not in data]
            
            if missing_keys:
                self.logger.error(f"❌ Fehlende Pflichtfelder: {missing_keys}")
                return False
                
            # Prüfe Geometrietyp
            geom = data.get('geometry')
            if not isinstance(geom, (Polygon, MultiPolygon)):
                self.logger.error("❌ Ungültiger Geometrietyp")
                return False
                
            # Prüfe Gebäudetyp
            building_type = data.get('type')
            valid_types = self.citygml_config.get('valid_building_types', [])
            
            if valid_types and building_type not in valid_types:
                self.logger.warning(f"⚠️ Unbekannter Gebäudetyp: {building_type}")
                
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Fehler bei der CityGML-Validierung: {str(e)}")
            return False 
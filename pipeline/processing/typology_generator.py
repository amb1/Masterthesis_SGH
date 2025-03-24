"""Typology Generator für die Erstellung der Gebäudetypologie-Datei."""

from typing import Dict, Any, List, Optional
import geopandas as gpd
import pandas as pd
from ..processing.base_processor import BaseProcessor

class TypologyGenerator(BaseProcessor):
    """Generator für die Erstellung der Gebäudetypologie."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialisiere den TypologyGenerator.
        
        Args:
            config: Konfigurationsdaten aus global.yml
        """
        super().__init__(config)
        
    def create_typology(self, buildings_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Erstelle die Gebäudetypologie aus den Gebäudedaten.
        
        Args:
            buildings_gdf: GeoDataFrame mit Gebäudedaten
            
        Returns:
            GeoDataFrame mit der Gebäudetypologie
        """
        if buildings_gdf.empty:
            raise ValueError("Keine Gebäude für Typology-Erstellung vorhanden")
            
        # Extrahiere relevante Attribute
        typology_data = {
            'building_id': [],
            'year_built': [],
            'height': [],
            'floors': [],
            'use_type': [],
            'construction_type': [],
            'geometry': []
        }
        
        for idx, building in buildings_gdf.iterrows():
            typology_data['building_id'].append(building.get('building_id', f'B{idx}'))
            typology_data['year_built'].append(building.get('year_of_construction', None))
            typology_data['height'].append(building.get('height', None))
            typology_data['floors'].append(building.get('floors', None))
            typology_data['use_type'].append(building.get('building_type', 'RESIDENTIAL'))
            typology_data['construction_type'].append(self._determine_construction_type(building))
            typology_data['geometry'].append(building.geometry)
            
        # Erstelle GeoDataFrame
        typology_gdf = gpd.GeoDataFrame(
            typology_data,
            geometry='geometry',
            crs=buildings_gdf.crs
        )
        
        return typology_gdf
        
    def _determine_construction_type(self, building: pd.Series) -> str:
        """Bestimme den Konstruktionstyp basierend auf Gebäudeattributen.
        
        Args:
            building: Pandas Series mit Gebäudeattributen
            
        Returns:
            String mit dem Konstruktionstyp
        """
        year = building.get('year_of_construction', 2000)
        
        if year < 1919:
            return 'HISTORICAL'
        elif year < 1945:
            return 'TRADITIONAL'
        elif year < 1980:
            return 'MODERN'
        else:
            return 'CONTEMPORARY'
            
    def export_typology(self, typology_gdf: gpd.GeoDataFrame, output_path: str) -> None:
        """Exportiere die Gebäudetypologie als Shapefile.
        
        Args:
            typology_gdf: GeoDataFrame mit der Gebäudetypologie
            output_path: Pfad für die Ausgabedatei
        """
        typology_gdf.to_file(output_path, driver=self.config.get('processing', {}).get('file_formats', {}).get('shp_driver', 'ESRI Shapefile')) 
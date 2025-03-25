"""
End-to-End Tests für die Gebäudedaten-Pipeline.

Diese Tests überprüfen den vollständigen Durchlauf der Pipeline von der
Datenbeschaffung bis zur Ausgabe.
"""

import pytest
import pandas as pd
import geopandas as gpd
import yaml
from shapely.geometry import Polygon
import logging
from pathlib import Path

from pipeline.orchestrator import PipelineOrchestrator
from pipeline.data_sources.citygml_fetcher import fetch_citygml_buildings
from pipeline.data_sources.wfs_fetcher import fetch_wfs_buildings
from pipeline.data_sources.osm_fetcher import fetch_osm_data

# Test-Logger konfigurieren
logger = logging.getLogger(__name__)

class TestPipelineE2E:
    @pytest.fixture
    def test_config(self):
        """Lädt die Test-Konfiguration."""
        with open("tests/fixtures/config/test_config.yml") as f:
            return yaml.safe_load(f)
    
    @pytest.fixture
    def test_data(self):
        """Erstellt Test-Geodaten."""
        # Erstelle ein einfaches Polygon für Testdaten
        polygon = Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])
        
        # CityGML Gebäude
        citygml_data = gpd.GeoDataFrame({
            'geometry': [polygon],
            'height': [10.0],
            'floors': [3],
            'year_built': [1950],
            'building_type': ['RESIDENTIAL']
        })
        
        # WFS Gebäude
        wfs_data = gpd.GeoDataFrame({
            'geometry': [polygon],
            'GEBAEUDE_HOEHE': [12.0],
            'GESCHOSSE': [4],
            'BAUJAHR': [1955],
            'GEBAEUDEART': ['W4.1.-soz.u.gemeinn.Wohnb.-Baulückenbebauungen']
        })
        
        # OSM Gebäude und Straßen
        osm_buildings = gpd.GeoDataFrame({
            'geometry': [polygon],
            'height': [11.0],
            'building:levels': [3],
            'start_date': [1952],
            'building': ['residential']
        })
        
        osm_streets = gpd.GeoDataFrame({
            'geometry': [polygon],
            'highway': ['residential'],
            'name': ['Teststraße']
        })
        
        return {
            'citygml': citygml_data,
            'wfs': wfs_data,
            'osm_buildings': osm_buildings,
            'osm_streets': osm_streets
        }
    
    @pytest.fixture
    def orchestrator(self, test_config):
        """Initialisiert den PipelineOrchestrator mit Testkonfiguration."""
        return PipelineOrchestrator(config_path="tests/fixtures/config/test_config.yml")
    
    def test_pipeline_complete_flow(self, orchestrator, test_data, mocker):
        """Testet den kompletten Durchlauf der Pipeline."""
        # Mock der Datenquellen-Funktionen
        mocker.patch(
            'pipeline.data_sources.citygml_fetcher.fetch_citygml_buildings',
            return_value=test_data['citygml']
        )
        mocker.patch(
            'pipeline.data_sources.wfs_fetcher.fetch_wfs_buildings',
            return_value=test_data['wfs']
        )
        mocker.patch(
            'pipeline.data_sources.osm_fetcher.fetch_osm_data',
            side_effect=[test_data['osm_buildings'], test_data['osm_streets']]
        )
        
        # Pipeline ausführen
        result = orchestrator.run_pipeline()
        
        # Überprüfungen
        assert result is True, "Pipeline-Ausführung sollte erfolgreich sein"
    
    def test_pipeline_data_quality(self, orchestrator, test_data, mocker):
        """Testet die Datenqualität der Pipeline-Ausgabe."""
        # Mocks wie im vorherigen Test
        mocker.patch(
            'pipeline.data_sources.citygml_fetcher.fetch_citygml_buildings',
            return_value=test_data['citygml']
        )
        mocker.patch(
            'pipeline.data_sources.wfs_fetcher.fetch_wfs_buildings',
            return_value=test_data['wfs']
        )
        mocker.patch(
            'pipeline.data_sources.osm_fetcher.fetch_osm_data',
            side_effect=[test_data['osm_buildings'], test_data['osm_streets']]
        )
        
        # Pipeline ausführen
        orchestrator.run_pipeline()
        
        # Überprüfe die verarbeiteten Daten
        processed_data = orchestrator._process_data(
            test_data['citygml'],
            test_data['wfs'],
            {'buildings': test_data['osm_buildings'], 'streets': test_data['osm_streets']}
        )
        
        # Qualitätsprüfungen
        assert isinstance(processed_data, dict), "Verarbeitete Daten sollten ein Dictionary sein"
        assert 'buildings' in processed_data, "Verarbeitete Daten sollten Gebäude enthalten"
        
        buildings = processed_data['buildings']
        assert isinstance(buildings, gpd.GeoDataFrame), "Gebäudedaten sollten ein GeoDataFrame sein"
        assert not buildings.empty, "Gebäudedaten sollten nicht leer sein"
        assert all(buildings.geometry.is_valid), "Alle Geometrien sollten gültig sein"
        
        # Überprüfe erforderliche Attribute
        required_columns = ['height', 'floors', 'year_built', 'building_type']
        for col in required_columns:
            assert col in buildings.columns, f"Spalte {col} fehlt in den verarbeiteten Daten"
    
    def test_pipeline_error_handling(self, orchestrator, test_data, mocker):
        """Testet die Fehlerbehandlung der Pipeline."""
        # Mock CityGML-Fetcher um einen Fehler zu simulieren
        mocker.patch(
            'pipeline.data_sources.citygml_fetcher.fetch_citygml_buildings',
            side_effect=Exception("Simulierter CityGML Fehler")
        )
        
        # Pipeline ausführen
        result = orchestrator.run_pipeline()
        
        # Überprüfungen
        assert result is False, "Pipeline sollte bei Fehlern False zurückgeben"
    
    def test_pipeline_empty_data(self, orchestrator, mocker):
        """Testet das Verhalten der Pipeline mit leeren Eingabedaten."""
        # Mock der Datenquellen mit leeren DataFrames
        empty_gdf = gpd.GeoDataFrame()
        mocker.patch(
            'pipeline.data_sources.citygml_fetcher.fetch_citygml_buildings',
            return_value=empty_gdf
        )
        mocker.patch(
            'pipeline.data_sources.wfs_fetcher.fetch_wfs_buildings',
            return_value=empty_gdf
        )
        mocker.patch(
            'pipeline.data_sources.osm_fetcher.fetch_osm_data',
            return_value=empty_gdf
        )
        
        # Pipeline ausführen
        result = orchestrator.run_pipeline()
        
        # Überprüfungen
        assert result is False, "Pipeline sollte bei leeren Daten False zurückgeben" 
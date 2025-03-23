"""
Tests für die CEA-Verarbeitungskomponenten.
"""

import pytest
import logging
import click
from click.testing import CliRunner
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from cli.run_cea import run_cea, CEAProcessingError, validate_paths
from pipeline.orchestrator import PipelineError
from core.config_manager import load_config
from pipeline.data_sources.citygml_fetcher import CityGMLBuildingProcessor
from pipeline.output.writer import write_output
import os
import geopandas as gpd
from shapely.geometry import Polygon

@pytest.fixture
def mock_logger():
    """Fixture für einen Mock-Logger."""
    with patch('cli.run_cea.logger') as mock:
        yield mock

@pytest.fixture
def test_config():
    """Fixture für eine Test-Konfiguration."""
    return {
        'input': {
            'citygml': 'data/test.gml'
        },
        'output': {
            'formats': ['geojson', 'shp']
        }
    }

class TestConfigManager:
    """Tests für das Konfigurationsmanagement."""
    
    def test_load_config_success(self, tmp_path):
        """Test: Erfolgreiche Konfigurationsladung."""
        config_path = tmp_path / "test_config.yml"
        config_path.write_text("""
        input:
          citygml: data/test.gml
        output:
          formats: 
            - geojson
            - shp
        """)
        
        config = load_config(str(config_path))
        assert config['input']['citygml'] == 'data/test.gml'
        assert 'geojson' in config['output']['formats']
    
    def test_load_config_file_not_found(self):
        """Test: Konfigurationsdatei nicht gefunden."""
        with pytest.raises(FileNotFoundError) as exc:
            load_config("nicht_vorhanden.yml")
        assert "nicht gefunden" in str(exc.value)

class TestCityGMLFetcher:
    """Tests für den CityGML-Fetcher."""
    
    def test_fetch_citygml_missing_file(self):
        mock_parse = MagicMock()
        mock_parse.side_effect = FileNotFoundError("nicht_vorhanden.gml")
        
        config = {"citygml": {"crs": "EPSG:31256"}}
        processor = CityGMLBuildingProcessor(config)
        
        with patch("pipeline.data_sources.citygml_fetcher.etree.parse", mock_parse, create=True):
            with pytest.raises(FileNotFoundError):
                processor.extract_buildings("nicht_vorhanden.gml")

    def test_fetch_citygml_success(self):
        # Mock für das Gebäude
        mock_building = MagicMock()
        mock_building.findall.return_value = [mock_building]
        mock_building.find.return_value.get.return_value = "EPSG:31256"
        
        # Mock für die Geometrie
        mock_geometry = MagicMock()
        mock_geometry.findall.return_value = [MagicMock()]
        mock_building.find.return_value = mock_geometry
        
        # Mock für das XML-Parsing
        mock_root = MagicMock()
        mock_root.findall.return_value = [mock_building]
        mock_parse = MagicMock()
        mock_parse.return_value.getroot.return_value = mock_root
        
        # Mock für GeoDataFrame
        mock_gdf = MagicMock()
        mock_gdf_class = MagicMock(return_value=mock_gdf)
        
        config = {"citygml": {"crs": "EPSG:31256"}}
        processor = CityGMLBuildingProcessor(config)
        
        with patch("pipeline.data_sources.citygml_fetcher.etree.parse", mock_parse), \
             patch("geopandas.GeoDataFrame", mock_gdf_class), \
             patch.object(processor, "_extract_geometry", return_value=MagicMock()):
            result = processor.extract_buildings("test.gml")
            assert result is not None
            assert isinstance(result, MagicMock)

class TestWriter:
    """Tests für das Writer-Modul."""
    
    def test_write_output_success(self, tmp_path):
        # Erstelle ein echtes GeoDataFrame für den Test
        geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        data = {"geometry": [geometry], "attribute": ["test"]}
        gdf = gpd.GeoDataFrame(data, geometry="geometry")
        
        # Erstelle Output-Verzeichnis
        output_dir = tmp_path / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Führe Test durch
        with patch.object(gdf, "to_file") as mock_to_file:
            test_data = {"test": gdf}
            write_output(test_data, output_formats=["geojson", "shp"], output_dir=output_dir)
            
            expected_calls = [
                call(output_dir / "test.geojson", driver="GeoJSON"),
                call(output_dir / "test.shp", driver="ESRI Shapefile")
            ]
            mock_to_file.assert_has_calls(expected_calls, any_order=True)
            assert mock_to_file.call_count == 2

class TestPipelineOrchestration:
    """Tests für die Pipeline-Orchestrierung."""
    
    def test_validate_paths_success(self, tmp_path):
        """Test: Erfolgreiche Pfadvalidierung."""
        config = tmp_path / "config.yml"
        data = tmp_path / "data"
        output = tmp_path / "output"
        
        config.touch()
        
        config_path, data_path, output_path = validate_paths(
            str(config),
            str(data),
            str(output)
        )
        
        assert config_path.exists()
        assert data_path.exists()
        assert output_path.exists()
    
    def test_validate_paths_missing_config(self, tmp_path):
        """Test: Fehlende Konfigurationsdatei."""
        with pytest.raises(CEAProcessingError) as exc:
            validate_paths(
                str(tmp_path / "nicht_vorhanden.yml"),
                str(tmp_path / "data"),
                str(tmp_path / "output")
            )
        assert "nicht gefunden" in str(exc.value)
    
    def test_validate_paths_permission_error(self, tmp_path):
        """Test: Fehlende Schreibrechte."""
        config = tmp_path / "config.yml"
        config.touch()
        
        with patch('cli.run_cea.os.access', return_value=False):
            with pytest.raises(CEAProcessingError) as exc:
                validate_paths(
                    str(config),
                    str(tmp_path / "data"),
                    str(tmp_path / "output")
                )
            assert "Schreibrechte" in str(exc.value)

@pytest.mark.integration
class TestEndToEnd:
    """End-to-End Tests für die gesamte Pipeline."""
    
    def test_run_cea_success(self, tmp_path, mock_logger):
        """Test: Erfolgreicher Durchlauf der Pipeline."""
        config = tmp_path / "config.yml"
        config.touch()
        
        with patch('cli.run_cea.PipelineOrchestrator') as mock_orchestrator:
            mock_instance = mock_orchestrator.return_value
            mock_instance.run_pipeline.return_value = True
            
            result = CliRunner().invoke(
                run_cea,
                ['--config', str(config),
                 '--data-dir', str(tmp_path / "data"),
                 '--output-dir', str(tmp_path / "output")]
            )
            
            assert result.exit_code == 0
            mock_logger.info.assert_any_call("🚀 Starte CEA-Verarbeitung...")
            mock_logger.info.assert_any_call("✅ CEA-Verarbeitung erfolgreich abgeschlossen")
    
    def test_run_cea_citygml_error(self, tmp_path, mock_logger):
        """Test: Fehler bei CityGML-Konfiguration."""
        config = tmp_path / "config.yml"
        config.touch()
        
        with patch('cli.run_cea.PipelineOrchestrator') as mock_orchestrator:
            mock_orchestrator.side_effect = PipelineError("CityGML Eingabedatei nicht definiert", "fetch_data")
            
            result = CliRunner().invoke(
                run_cea,
                ['--config', str(config),
                 '--data-dir', str(tmp_path / "data"),
                 '--output-dir', str(tmp_path / "output")]
            )
            
            assert result.exit_code != 0
            assert "CityGML" in mock_logger.error.call_args[0][0] 
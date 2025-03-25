import pytest
import geopandas as gpd
from pathlib import Path
from pipeline.processing.cea_processor import CEAProcessor
from pipeline.data_sources.citygml_fetcher import CityGMLFetcher
from pipeline.data_sources.wfs_fetcher import WFSFetcher

def test_cea_pipeline_integration(sample_site_gdf, cea_mapping_config, test_outputs_dir):
    """Integrationstests für die gesamte CEA-Pipeline"""
    # Pipeline-Instanz erstellen
    processor = CEAProcessor(cea_mapping_config)
    
    # Testdaten laden
    citygml_fetcher = CityGMLFetcher()
    wfs_fetcher = WFSFetcher()
    
    # Verarbeitung durchführen
    result = processor.process_site(
        site_polygon=sample_site_gdf,
        citygml_data=citygml_fetcher.fetch_buildings(),
        wfs_data=wfs_fetcher.fetch_buildings()
    )
    
    # Ergebnisvalidierung
    assert isinstance(result, gpd.GeoDataFrame)
    assert not result.empty
    assert "Name" in result.columns
    assert "REFERENCE" in result.columns
    assert "height_ag" in result.columns
    assert "floors_ag" in result.columns
    
    # Prüfe erweiterte Felder
    assert "street" in result.columns
    assert "house_no" in result.columns
    assert "postcode" in result.columns
    assert "city" in result.columns
    assert "country" in result.columns
    
    # Prüfe Nutzungstypen
    assert "1ST_USE" in result.columns
    assert "2ND_USE" in result.columns
    assert "3RD_USE" in result.columns
    
    # Validiere Datentypen und Wertebereiche
    assert result["height_ag"].between(2.0, 200.0).all()
    assert result["floors_ag"].between(1, 100).all()
    
    # Prüfe Name-Format
    assert all(result["Name"].str.contains("_"))
    
    # Prüfe REFERENCE-Format
    assert all(result["REFERENCE"].str.startswith(("BLDG_", "WFS_")))

def test_cea_pipeline_validation(sample_site_gdf, cea_mapping_config, sample_validation_config):
    """Test der Validierungsregeln in der Pipeline"""
    processor = CEAProcessor(cea_mapping_config, validation_config=sample_validation_config)
    
    # Erstelle ungültige Testdaten
    invalid_data = gpd.GeoDataFrame({
        "height_ag": [1.0, 250.0],  # Ungültige Höhen
        "floors_ag": [0, 150],      # Ungültige Geschosszahlen
        "year_built": [1700, 2025]  # Ungültige Jahre
    }, geometry=sample_site_gdf.geometry.iloc[:2])
    
    # Prüfe, ob Validierungsfehler erkannt werden
    with pytest.raises(ValueError):
        processor.validate_buildings(invalid_data)

def test_cea_pipeline_source_priority(sample_site_gdf, cea_mapping_config):
    """Test der Datenquellen-Priorisierung in der Pipeline"""
    processor = CEAProcessor(cea_mapping_config)
    
    # Simuliere konfliktäre Daten
    citygml_data = gpd.GeoDataFrame({
        "REFERENCE": ["BLDG_001"],
        "height_ag": [15.5],
        "floors_ag": [4]
    }, geometry=sample_site_gdf.geometry.iloc[:1])
    
    wfs_data = gpd.GeoDataFrame({
        "REFERENCE": ["WFS_001"],
        "height_ag": [16.0],
        "floors_ag": [5]
    }, geometry=sample_site_gdf.geometry.iloc[:1])
    
    # Verarbeite die Daten
    result = processor.process_site(
        site_polygon=sample_site_gdf,
        citygml_data=citygml_data,
        wfs_data=wfs_data
    )
    
    # CityGML sollte Priorität haben
    assert result.iloc[0]["REFERENCE"] == "BLDG_001"
    assert result.iloc[0]["height_ag"] == 15.5
    assert result.iloc[0]["floors_ag"] == 4

def test_cea_pipeline_output_formats(sample_site_gdf, cea_mapping_config, test_outputs_dir):
    """Test der Ausgabeformate der Pipeline"""
    processor = CEAProcessor(cea_mapping_config)
    
    # Verarbeitung durchführen
    result = processor.process_site(
        site_polygon=sample_site_gdf,
        citygml_data=None,  # Leere Daten für Test
        wfs_data=None
    )
    
    # GeoJSON Export
    geojson_path = test_outputs_dir / "buildings.geojson"
    processor.export_geojson(result, geojson_path)
    assert geojson_path.exists()
    
    # Shapefile Export
    shp_path = test_outputs_dir / "buildings.shp"
    processor.export_shapefile(result, shp_path)
    assert shp_path.exists()
    
    # Validiere Exporte
    geojson_data = gpd.read_file(geojson_path)
    assert not geojson_data.empty
    assert all(col in geojson_data.columns for col in result.columns)
    
    shp_data = gpd.read_file(shp_path)
    assert not shp_data.empty
    assert all(col in shp_data.columns for col in result.columns) 
import pytest
import geopandas as gpd
from pathlib import Path
import logging
from pipeline.data_sources.citygml_fetcher import CityGMLFetcher
from pipeline.data_sources.wfs_fetcher import ViennaWFS
from pipeline.geometry.site_polygon import create_site_polygon

# Logger einrichten
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@pytest.fixture
def test_data_path():
    """Pfad zu den Testdaten"""
    return Path(__file__).parent / "fixtures" / "citygml" / "test_building.gml"

@pytest.fixture
def wfs_config():
    """Test-Konfiguration für Vienna WFS"""
    return {
        'url': 'https://data.wien.gv.at/daten/geo',
        'version': '1.1.0',
        'srsName': 'EPSG:31256',
        'streams': [
            {
                'name': 'Gebäudeinfo',
                'layer': 'ogdwien:GEBAEUDEINFOOGD',
                'priority': 1,
                'fields': ['OBJECTID', 'geometry', 'BAUJAHR'],
                'mapping': {
                    'building_id': 'OBJECTID',
                    'geometry': 'geometry',
                    'construction_year': 'BAUJAHR'
                }
            }
        ],
        'processing': {
            'clip_to_site': True
        }
    }

def test_integration_workflow(test_data_path, wfs_config, tmp_path):
    """Test des Gesamtablaufs: CityGML -> Site Polygon -> WFS"""
    
    logger.info("🔄 Starte Integrations-Test")
    
    # 1. CityGML verarbeiten
    logger.info("📥 Verarbeite CityGML-Datei")
    citygml_fetcher = CityGMLFetcher(test_data_path)
    buildings_gdf = citygml_fetcher.get_buildings()
    assert not buildings_gdf.empty, "Keine Gebäude aus CityGML extrahiert"
    
    # 2. Site-Polygon erstellen
    logger.info("🗺️ Erstelle Site-Polygon")
    site_polygon = create_site_polygon(buildings_gdf)
    assert site_polygon is not None, "Site-Polygon konnte nicht erstellt werden"
    
    # Speichere Site-Polygon für spätere Verwendung
    site_path = tmp_path / "site.shp"
    site_polygon.to_file(site_path)
    logger.info(f"💾 Site-Polygon gespeichert: {site_path}")
    
    # 3. WFS-Daten abrufen
    logger.info("🌐 Rufe WFS-Daten ab")
    wfs = ViennaWFS(config=wfs_config)
    
    # Transformiere Site-Polygon ins Wiener Koordinatensystem
    site_polygon_vienna = site_polygon.to_crs('EPSG:31256')
    
    # Hole WFS-Daten
    results = wfs.process_site(site_polygon_vienna)
    
    # Validiere Ergebnisse
    assert isinstance(results, dict), "WFS-Ergebnisse sollten ein Dictionary sein"
    assert 'Gebäudeinfo' in results, "Gebäudeinfo-Stream nicht in Ergebnissen"
    
    gebaeude_info = results['Gebäudeinfo']
    assert isinstance(gebaeude_info, gpd.GeoDataFrame), "Gebäudeinfo sollte ein GeoDataFrame sein"
    assert not gebaeude_info.empty, "Keine Gebäudedaten vom WFS erhalten"
    
    # Speichere WFS-Ergebnisse
    for name, gdf in results.items():
        output_path = tmp_path / f"wfs_{name}.shp"
        gdf.to_file(output_path)
        logger.info(f"💾 WFS-Daten gespeichert: {output_path}")
    
    logger.info("✅ Integrations-Test erfolgreich abgeschlossen") 
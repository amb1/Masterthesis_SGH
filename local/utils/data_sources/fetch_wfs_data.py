from owslib.wfs import WebFeatureService
import geopandas as gpd
import yaml
from typing import Optional
from pathlib import Path
import logging

# Logger einrichten
logger = logging.getLogger("ViennaWFS")
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class ViennaWFS:
    """Klasse für den Zugriff auf WFS-Dienste der Stadt Wien"""

    def __init__(self, wfs_config=None):
        """Initialisiert die Verbindung zum WFS-Service"""
        self.wfs_url = 'https://data.wien.gv.at/daten/geo'
        self.wfs_version = '1.1.0'
        self.crs = 'urn:x-ogc:def:crs:EPSG:31256'
        self.wfs = WebFeatureService(url=self.wfs_url, version=self.wfs_version)
        
        # Lade die normalisierte WFS-Konfiguration
        config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "data_sources" / "vienna_wfs_normalized.yml"
        with open(config_path, "r", encoding="utf-8") as file:
            self.base_config = yaml.safe_load(file)
        
        self.wfs_config = wfs_config or []
        logger.info(f"WFS-Service initialisiert: {self.wfs_url}")

    def fetch_building_model(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt das Baukörpermodell"""
        try:
            logger.info("Lade Baukörpermodell...")
            # Prüfe ob bbox gültige Werte enthält
            if bbox is None or any(map(lambda x: x != x, bbox)):  # Prüft auf NaN
                logger.error("❌ Ungültige Bounding Box für WFS-Abfrage")
                return None
            
            response = self.wfs.getfeature(
                typename='ogdwien:FMZKBKMOGD',
                bbox=bbox,
                srsname=self.crs
            )
            
            buildings_gdf = gpd.read_file(response)

            if 'geometry' not in buildings_gdf.columns:
                logger.error("❌ WFS-Daten enthalten keine Geometrie! Überprüfe die Abfrage.")
                return None

            buildings_gdf["height"] = buildings_gdf["O_KOTE"].astype(float) - buildings_gdf["U_KOTE"].astype(float)

            logger.info(f"✅ {len(buildings_gdf)} Gebäude geladen")
            return buildings_gdf

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden des Baukörpermodells: {str(e)}", exc_info=True)
            return None

    def fetch_building_typology(self, bbox) -> Optional[gpd.GeoDataFrame]:
        """Lädt die Gebäudetypologie für den gegebenen Bereich"""
        try:
            logger.info("Lade Gebäudetypologie...")
            response = self.wfs.getfeature(
                typename='ogdwien:GEBAEUDETYPOGD',
                bbox=bbox,
                srsname=self.crs
            )
            typology_gdf = gpd.read_file(response)

            if 'geometry' not in typology_gdf.columns:
                logger.error("❌ Fehler: WFS-Daten enthalten keine Geometrie!")
                return None

            return typology_gdf

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der Gebäudetypologie: {str(e)}", exc_info=True)
            return None
        

    def enrich_buildings(self, site_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Erweitert Gebäudedaten mit WFS-Daten und behält die Geometrie."""
        try:
            bbox = tuple(site_gdf.total_bounds)
            building_model = self.fetch_building_model(bbox)
            building_typology = self.fetch_building_typology(bbox)

            if building_model is not None and not building_model.empty:
                if 'geometry' not in building_model.columns:
                    print("❌ Fehler: 'geometry' fehlt in WFS-Building Model")
                    return site_gdf  # Rückgabe der Originaldaten mit Geometrie

                enriched_gdf = building_model.copy()

                if building_typology is not None and not building_typology.empty:
                    enriched_gdf = enriched_gdf.merge(building_typology, left_on="FMZK_ID", right_on="OBJECTID", how="left")

                # Sicherstellen, dass Geometrie erhalten bleibt
                enriched_gdf = gpd.GeoDataFrame(enriched_gdf, geometry='geometry', crs=site_gdf.crs)

                return enriched_gdf  # Rückgabe mit Geometrie

            return site_gdf  # Falls nichts geladen wurde, das Original zurückgeben

        except Exception as e:
            print(f"❌ Fehler bei der WFS-Anreicherung: {str(e)}")
            return site_gdf  # Fehler -> Rückgabe der Originaldaten mit Geometrie


    def fetch_layer(self, layer_name, bbox=None) -> Optional[gpd.GeoDataFrame]:
        """Lädt einen WFS Layer und validiert Geometrie"""
        try:
            logger.info(f"Lade WFS Layer: {layer_name}")
            typename = layer_name if "ogdwien:" in layer_name else f"ogdwien:{layer_name}"
            
            response = self.wfs.getfeature(
                typename=typename,
                bbox=bbox,
                srsname=self.crs
            )
            
            data_gdf = gpd.read_file(response)

            if data_gdf is None or data_gdf.empty:
                logger.warning(f"⚠️ Keine Daten für Layer {layer_name} erhalten")
                return None

            if 'geometry' not in data_gdf.columns:
                raise ValueError(f"❌ Fehler: 'geometry'-Spalte fehlt im WFS-DataFrame für {layer_name}")

            return gpd.GeoDataFrame(data_gdf, geometry='geometry', crs="EPSG:31256")

        except Exception as e:
            logger.error(f"❌ Fehler beim Laden des Layers {layer_name}: {str(e)}", exc_info=True)
            return None


def fetch_wfs_data(site_polygon, layer_name, config):
    """Lädt WFS-Daten basierend auf der Konfiguration"""
    try:
        logger.info(f"🔄 Starte WFS-Datenabruf für Layer: {layer_name}")

        # Initialisiere WFS-Service
        wfs = ViennaWFS(config.get('wfs_streams', []))

        # Stream-Konfiguration abrufen
        stream_config = next((s for s in wfs.wfs_config if s['layer'] == layer_name), None)
        if not stream_config:
            raise ValueError(f"⚠️ Keine Konfiguration gefunden für Layer: {layer_name}")

        logger.info(f"✅ WFS-Stream: {stream_config['name']}")

        # Lade WFS-Daten
        data = wfs.fetch_layer(layer_name, site_polygon.total_bounds if site_polygon is not None else None)

        if data is None or data.empty:
            logger.warning("⚠️ Keine WFS-Daten erhalten")
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")

        if 'geometry' not in data.columns:
            logger.error("❌ Fehler: 'geometry' fehlt in WFS-DataFrame")
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")

        return data

    except Exception as e:
        logger.error(f"❌ Fehler beim WFS-Abruf: {str(e)}", exc_info=True)
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:31256")


if __name__ == "__main__":
    print("🔎 WFS Daten Test-Modus")
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / "cfg" / "project_config.yml"
        with open(config_path, 'r', encoding="utf-8") as f:
            config = yaml.safe_load(f)

        from shapely.geometry import box
        test_bounds = (16.35, 48.20, 16.37, 48.22)
        test_polygon = box(*test_bounds)
        test_gdf = gpd.GeoDataFrame(geometry=[test_polygon], crs="EPSG:4326").to_crs("EPSG:31256")

        for stream in config.get('data_sources', {}).get('wfs_streams', []):
            try:
                data = fetch_wfs_data(test_gdf, stream['layer'], config['data_sources'])
                if data is not None:
                    print(f"✅ Stream-Test erfolgreich: {stream['name']}")
            except Exception as e:
                print(f"❌ Fehler bei Stream {stream['name']}: {str(e)}")

    except Exception as e:
        logger.error(f"❌ Fehler im Test-Modus: {str(e)}", exc_info=True)

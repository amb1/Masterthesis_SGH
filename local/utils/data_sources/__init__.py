"""
Dieses Paket enthält Module zum Abrufen von Daten aus verschiedenen Quellen.

Verfügbare Module:
- fetch_citygml_buildings: Funktionen zum Abrufen von Gebäudedaten aus CityGML
- fetch_osm_buildings: Funktionen zum Abrufen von Gebäudedaten aus OpenStreetMap
- fetch_osm_streets: Funktionen zum Abrufen von Straßendaten aus OpenStreetMap
- fetch_wfs_data: Funktionen zum Abrufen von Daten aus WFS-Diensten
"""

from pathlib import Path
import sys

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from .fetch_wfs_data import ViennaWFS
from .fetch_osm_buildings import fetch_surrounding_buildings
from .fetch_osm_streets import fetch_osm_streets

__all__ = [
    'ViennaWFS',
    'fetch_surrounding_buildings',
    'fetch_osm_streets'
]
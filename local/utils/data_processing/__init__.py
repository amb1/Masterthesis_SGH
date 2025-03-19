"""
Dieses Paket enthält Module zur Verarbeitung von Gebäudedaten.

Verfügbare Module:
- create_site_polygon: Funktionen zum Erstellen eines Site-Polygons
- base_building_processor: Basis-Implementierung für Gebäudeverarbeitung
- cea_building_processor: CEA-spezifische Gebäudeverarbeitung
"""

from pathlib import Path
import sys

# Füge das Root-Verzeichnis zum Python-Path hinzu
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

from .create_site_polygon import create_site_polygon, save_site_polygon
from .base_building_processor import BuildingProcessorInterface, BasicBuildingProcessor
from .cea_building_processor import CEABuildingProcessor

__all__ = [
    'create_site_polygon',
    'save_site_polygon',
    'BuildingProcessorInterface',
    'BasicBuildingProcessor',
    'CEABuildingProcessor'
]

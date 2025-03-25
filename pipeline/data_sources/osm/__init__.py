"""
OSM-Modul für die Verarbeitung von OpenStreetMap-Daten.
"""

from .client import OSMBaseClient
from .geometry import OSMGeometryProcessor
from .attributes import OSMAttributeProcessor
from .config import OSMConfig

__all__ = [
    'OSMBaseClient',
    'OSMGeometryProcessor',
    'OSMAttributeProcessor',
    'OSMConfig'
] 
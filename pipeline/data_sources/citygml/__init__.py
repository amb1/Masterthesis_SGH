"""
CityGML-Paket für die Verarbeitung von CityGML-Daten.
"""

from .config import CityGMLConfig, CityGMLConfigError
from .client import CityGMLBaseClient, XMLResolver
from .geometry import CityGMLGeometryProcessor
from .attributes import CityGMLAttributeProcessor
from .fetcher import ViennaCityGMLFetcher, fetch_citygml_buildings

__all__ = [
    'CityGMLConfig',
    'CityGMLConfigError',
    'CityGMLBaseClient',
    'XMLResolver',
    'CityGMLGeometryProcessor',
    'CityGMLAttributeProcessor',
    'ViennaCityGMLFetcher',
    'fetch_citygml_buildings'
] 
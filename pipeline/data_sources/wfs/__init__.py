"""
WFS-Modul für den Zugriff auf WFS-Dienste.
"""

from .client import WFSClient
from .config import WFSConfig
from .geometry import WFSGeometry
from .stream import WFSStream

__all__ = [
    'WFSClient',
    'WFSConfig',
    'WFSGeometry',
    'WFSStream'
] 
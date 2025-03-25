"""
WFS-Konfiguration für die Verarbeitung von WFS-Daten.
"""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

class WFSConfig:
    """Konfiguration für WFS-Operationen."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """Initialisiert die WFS-Konfiguration.
        
        Args:
            config: Optional[Dict] - Direkte Konfiguration
            config_path: Optional[str] - Pfad zur Konfigurationsdatei
        """
        self.logger = logging.getLogger(__name__)
        
        # Setze Standardwerte
        self._config = {
            'url': None,
            'version': '1.1.0',
            'timeout': 30,
            'srs_name': 'EPSG:31256',
            'streams': {},
            'is_wfs': True  # Markiere als WFS-Datenquelle
        }
        
        if config_path:
            self._load_config_file(config_path)
            
        if config:
            self._config.update(config)
            
        self.logger.info("✅ WFS-Konfiguration initialisiert")
        
    def _load_config_file(self, config_path: str) -> None:
        """Lädt die Konfiguration aus einer Datei.
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                if file_config:
                    self._config.update(file_config)
                else:
                    self.logger.warning("⚠️ Leere Konfigurationsdatei")
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Laden der Konfiguration: {str(e)}")
            
    @property
    def url(self) -> Optional[str]:
        """WFS Service URL."""
        return self._config.get('url')
        
    @property
    def version(self) -> str:
        """WFS Version."""
        return self._config.get('version', '1.1.0')
        
    @property
    def timeout(self) -> int:
        """Request Timeout in Sekunden."""
        return self._config.get('timeout', 30)
        
    @property
    def srs_name(self) -> str:
        """Koordinatensystem."""
        return self._config.get('srs_name', 'EPSG:31256')
        
    @property
    def streams(self) -> Dict[str, Any]:
        """Konfigurierte WFS-Streams."""
        return self._config.get('streams', {})
        
    @property
    def is_wfs(self) -> bool:
        """Gibt an ob es sich um WFS-Daten handelt."""
        return self._config.get('is_wfs', True) 
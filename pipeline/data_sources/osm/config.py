"""
Konfigurationsmanagement für OSM-Daten.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from core.config_manager import load_config as load_yaml_config

logger = logging.getLogger(__name__)

class OSMConfig:
    """Konfigurationsklasse für OSM-Daten."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialisiert die OSM-Konfiguration.
        
        Args:
            config: Optionales Konfigurationsobjekt
        """
        self._config = {}
        if config:
            # Übernehme die übergebene Konfiguration
            if 'buildings' in config:
                self._config['buildings'] = config['buildings']
            if 'streets' in config:
                self._config['streets'] = config['streets']
        else:
            self._load_config()
        
    def _load_config(self) -> None:
        """Lädt die OSM-Konfiguration aus der config.yml"""
        try:
            root_dir = Path(__file__).resolve().parent.parent.parent.parent
            osm_config_path = root_dir / 'config' / 'osm' / 'config.yml'
            
            if not osm_config_path.exists():
                logger.warning(f"⚠️ Keine OSM-Konfiguration gefunden unter {osm_config_path}")
                return
                
            config = load_yaml_config(osm_config_path)
            if not config or not isinstance(config, dict):
                logger.warning("⚠️ Ungültige OSM-Konfiguration")
                return
                
            self._config = config.get('osm', {})
            logger.info("✅ OSM-Konfiguration erfolgreich geladen")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden der OSM-Konfiguration: {str(e)}")
            
    @property
    def building_defaults(self) -> Dict[str, Any]:
        """Gibt die Standard-Gebäudeattribute zurück."""
        return self._config.get('buildings', {}).get('defaults', {})
        
    @property
    def street_types(self) -> Dict[str, Any]:
        """Gibt die konfigurierten Straßentypen zurück."""
        return self._config.get('streets', {}).get('street_types', {})
        
    @property
    def buffer_distance(self) -> int:
        """Gibt die Buffer-Distanz für Umgebungsabfragen zurück."""
        return self._config.get('buildings', {}).get('buffer_distance', 100)
        
    @property
    def network_type(self) -> str:
        """Gibt den Netzwerktyp für Straßenabfragen zurück."""
        return self._config.get('streets', {}).get('network_type', 'all') 
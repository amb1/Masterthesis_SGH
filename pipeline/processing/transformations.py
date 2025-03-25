"""
Transformationsfunktionen für Gebäudedaten.

Migrated from local/utils/transformations.py

Dieses Modul enthält Funktionen zur Transformation von Gebäudedaten,
einschließlich Typenmapping, Periodenbestimmung und Wertkonvertierung.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any, TypeVar, Callable, List
import logging
import random
from core.config_manager import load_config
from core.logging_config import LoggedOperation

# Logger konfigurieren
logger = logging.getLogger(__name__)

T = TypeVar('T')

def get_period_suffix(year: int) -> str:
    """Bestimmt das Periodensuffix basierend auf dem Baujahr."""
    if year <= 1859:
        return "_A"
    elif year <= 1918:
        return "_B"
    elif year <= 1948:
        return "_C"
    elif year <= 1957:
        return "_D"
    elif year <= 1968:
        return "_E"
    elif year <= 1978:
        return "_F"
    elif year <= 1983:
        return "_G"
    elif year <= 1994:
        return "_H"
    elif year <= 2001:
        return "_I"
    elif year <= 2009:
        return "_J"
    elif year <= 2015:
        return "_K"
    else:
        return "_L"

def map_building_use(building_type: str, config_path: str = "config/wfs/stream_config.yml") -> str:
    """
    Mappt den WFS-Gebäudetyp auf einen CEA-Standard-Gebäudetyp für USE_TYPE.
    
    Args:
        building_type: Der Gebäudetyp aus dem WFS-Stream
        config_path: Pfad zur Konfigurationsdatei mit dem Mapping
        
    Returns:
        Der gemappte CEA-Gebäudetyp oder "MULTI_RES" als Standard
    """
    try:
        with LoggedOperation("Gebäudetyp-Mapping"):
            # Konvertiere String-Pfad zu Path-Objekt
            config_path = Path(config_path)
            if not config_path.is_absolute():
                config_path = Path(__file__).resolve().parent.parent.parent / config_path
                
            config = load_config(config_path)
            if not config:
                logger.warning("⚠️ Keine Konfiguration geladen")
                return "MULTI_RES"
                
            use_types = config.get('building_types', {}).get('use_type', {})
            
            # Direktes Mapping aus der Konfiguration
            if building_type in use_types:
                return use_types[building_type]
                
            # Fallback-Logik basierend auf Schlüsselwörtern
            building_type_lower = building_type.lower()
            if any(keyword in building_type_lower for keyword in ['handel', 'kaufhaus', 'einkauf']):
                return "RETAIL"
            elif any(keyword in building_type_lower for keyword in ['industrie', 'gewerbe', 'fabrik']):
                return "INDUSTRIAL"
            elif any(keyword in building_type_lower for keyword in ['büro', 'verwaltung', 'öffentlich']):
                return "OFFICE"
            elif any(keyword in building_type_lower for keyword in ['hotel', 'pension']):
                return "HOTEL"
            elif any(keyword in building_type_lower for keyword in ['krankenhaus', 'spital', 'pflege']):
                return "HOSPITAL"
            elif any(keyword in building_type_lower for keyword in ['villa', 'einfamilienhaus']):
                return "SINGLE_RES"
            
            # Standard-Rückgabewert
            return "MULTI_RES"
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Mapping des Gebäudetyps: {str(e)}")
        return "MULTI_RES"

def get_standard_prefix(building_type: str, config_path: str = "config/wfs/stream_config.yml") -> str:
    """
    Ermittelt den STANDARD-Prefix basierend auf dem Gebäudetyp.
    
    Args:
        building_type: Der Gebäudetyp aus dem WFS-Stream
        config_path: Pfad zur Konfigurationsdatei
        
    Returns:
        Der STANDARD-Prefix (z.B. "MFH", "SFH", etc.)
    """
    try:
        with LoggedOperation("Standard-Prefix ermitteln"):
            # Konvertiere String-Pfad zu Path-Objekt
            config_path = Path(config_path)
            if not config_path.is_absolute():
                config_path = Path(__file__).resolve().parent.parent.parent / config_path
                
            config = load_config(config_path)
            if not config:
                logger.warning("⚠️ Keine Konfiguration geladen")
                return "MFH"
                
            standard_prefixes = config.get('building_types', {}).get('standard_prefix', {})
            
            # Direktes Mapping aus der Konfiguration
            if building_type in standard_prefixes:
                return standard_prefixes[building_type]
                
            # Fallback-Logik
            building_type_lower = building_type.lower()
            if any(keyword in building_type_lower for keyword in ['handel', 'kaufhaus', 'einkauf']):
                return "SCR"
            elif any(keyword in building_type_lower for keyword in ['industrie', 'gewerbe', 'fabrik']):
                return "IND"
            elif any(keyword in building_type_lower for keyword in ['büro', 'verwaltung', 'öffentlich']):
                return "OFB"
            elif any(keyword in building_type_lower for keyword in ['hotel', 'pension']):
                return "HOT"
            elif any(keyword in building_type_lower for keyword in ['krankenhaus', 'spital', 'pflege']):
                return "HOS"
            elif any(keyword in building_type_lower for keyword in ['villa', 'einfamilienhaus']):
                return "SFH"
            
            # Standard-Rückgabewert
            return "MFH"
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Ermitteln des STANDARD-Prefix: {str(e)}")
        return "MFH"

def combine_building_standard(building_type: str, year: int, config_path: str = "config/wfs/stream_config.yml") -> str:
    """
    Kombiniert den Gebäudetyp und das Baujahr zu einem CEA-Standard.
    
    Args:
        building_type: Der Gebäudetyp aus dem WFS-Stream
        year: Das Baujahr des Gebäudes
        config_path: Pfad zur Konfigurationsdatei
        
    Returns:
        Der kombinierte CEA-Standard (z.B. "MFH_C")
    """
    try:
        with LoggedOperation("CEA-Standard bestimmen"):
            # Hole den STANDARD-Prefix
            standard_prefix = get_standard_prefix(building_type, config_path)
            
            # Bestimme das Periodensuffix
            period_suffix = get_period_suffix(year)
            
            # Kombiniere Prefix und Periode
            return f"{standard_prefix}{period_suffix}"
            
    except Exception as e:
        logger.error(f"❌ Fehler bei der Standardbestimmung: {str(e)}")
        return "MFH_E"  # Standardwert als Fallback

def shorten_id(osm_id: str) -> str:
    """Kürzt eine OSM-ID auf ein kompakteres Format.
    
    Args:
        osm_id: Original OSM-ID (z.B. "way/123456789")
    
    Returns:
        Gekürzte ID (z.B. "w123456789")
    """
    prefix_map = {
        "way": "w",
        "node": "n",
        "relation": "r"
    }
    
    type_str, id_str = osm_id.split("/")
    return f"{prefix_map.get(type_str, 'x')}{id_str}"

def transform_value(value: str, target_type: Callable[[str], T], default: Optional[T] = None) -> T:
    """Transformiert einen String-Wert in den Zieltyp.
    
    Args:
        value: Zu transformierender Wert
        target_type: Zieltypfunktion (z.B. float, int)
        default: Standardwert bei leerem Input
    
    Returns:
        Transformierter Wert
    
    Raises:
        ValueError: Bei ungültigem Input
    """
    if not value and default is not None:
        return default
    
    try:
        return target_type(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Ungültiger Wert '{value}' für Typ {target_type.__name__}") from e

def map_building_type(building_type: str) -> str:
    """Mappt den Gebäudetyp auf standardisierte Werte.
    
    Args:
        building_type: Original Gebäudetyp
    
    Returns:
        Standardisierter Gebäudetyp
    """
    mapping = {
        "residential": "RESIDENTIAL",
        "commercial": "OFFICE",
        "industrial": "INDUSTRIAL"
    }
    return mapping.get(building_type.lower(), "MIXED")

def map_construction_period(year: int) -> str:
    """Mappt das Baujahr auf eine Bauperiode.
    
    Args:
        year: Baujahr
    
    Returns:
        Bauperiode als String
    """
    if year < 1900:
        return "PRE-1900"
    
    decade = (year // 10) * 10
    return f"{decade}-{decade+9}"

def get_wfs_period(year: int, config: Dict[str, Any]) -> Optional[str]:
    """Bestimmt die WFS-Periode basierend auf dem Baujahr.
    
    Args:
        year: Baujahr des Gebäudes
        config: Konfigurationsobjekt mit Periodendefinitionen
        
    Returns:
        WFS-Periodenbezeichnung oder None wenn keine Zuordnung möglich
    """
    wfs_periods = config.get('building_classification', {}).get('periods', {}).get('wfs_periods', {})
    
    for period_name, period_data in wfs_periods.items():
        range_start, range_end = period_data.get('range', [None, None])
        if range_start and range_end:
            if range_start <= year <= range_end:
                return period_name
        elif range_start and not range_end:  # Für "nach 1945"
            if year >= range_start:
                return period_name
            
    return None

def distribute_to_detailed_period(wfs_period: str, config: Dict[str, Any]) -> str:
    """Verteilt eine WFS-Periode auf eine detaillierte Periode basierend auf Wahrscheinlichkeiten.
    
    Args:
        wfs_period: WFS-Periodenbezeichnung
        config: Konfigurationsobjekt mit Verteilungsdefinitionen
        
    Returns:
        Detaillierte Periodenbezeichnung (A-L)
    """
    try:
        # Hole die Verteilungsdefinition für die WFS-Periode
        period_config = config.get('building_classification', {}).get('periods', {}).get('wfs_periods', {}).get(wfs_period)
        if not period_config:
            logger.warning(f"⚠️ Keine Verteilungskonfiguration für Periode {wfs_period} gefunden")
            return "E"  # Standardwert als Fallback
            
        distribution = period_config.get('distribution', [])
        if not distribution:
            logger.warning(f"⚠️ Keine Verteilung für Periode {wfs_period} definiert")
            return "E"
            
        # Erstelle gewichtete Liste für die Auswahl
        periods = [d['period'] for d in distribution]
        weights = [d['weight'] for d in distribution]
        
        # Normalisiere Gewichte
        total_weight = sum(weights)
        normalized_weights = [w/total_weight for w in weights]
        
        # Wähle eine Periode basierend auf den Gewichten
        selected_period = random.choices(periods, normalized_weights, k=1)[0]
        
        return selected_period
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Periodenverteilung: {str(e)}")
        return "E"

def generate_random_year(period: str, config: Dict[str, Any]) -> int:
    """Generiert ein zufälliges Jahr innerhalb einer detaillierten Periode.
    
    Args:
        period: Detaillierte Periodenbezeichnung (A-L)
        config: Konfigurationsobjekt mit Periodendefinitionen
        
    Returns:
        Zufällig generiertes Jahr
    """
    try:
        # Hole die Periodendefinition
        period_config = config.get('building_classification', {}).get('periods', {}).get('detailed_periods', {}).get(period)
        if not period_config:
            logger.warning(f"⚠️ Keine Definition für Periode {period} gefunden")
            return 1970  # Standardwert als Fallback
            
        start_year = period_config.get('start', 1900)
        end_year = period_config.get('end', 2000)
        
        # Setze Standardwerte für None
        if start_year is None:
            start_year = 1800
        if end_year is None:
            end_year = 2025
            
        # Generiere zufälliges Jahr im Bereich
        return random.randint(start_year, end_year)
        
    except Exception as e:
        logger.error(f"❌ Fehler bei der Jahresgenerierung: {str(e)}")
        return 1970

def process_building_period(wfs_period: str, config: Dict[str, Any]) -> Tuple[str, int]:
    """Verarbeitet eine WFS-Periode zu einer detaillierten Periode und generiert ein passendes Jahr.
    
    Args:
        wfs_period: WFS-Periodenbezeichnung
        config: Konfigurationsobjekt
        
    Returns:
        Tuple aus (detaillierte_periode, generiertes_jahr)
    """
    with LoggedOperation("Periodenverarbeitung"):
        # Verteile auf detaillierte Periode
        detailed_period = distribute_to_detailed_period(wfs_period, config)
        
        # Generiere passendes Jahr
        year = generate_random_year(detailed_period, config)
        
        return detailed_period, year 
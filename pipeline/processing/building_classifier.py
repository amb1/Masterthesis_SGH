"""
Modul zur Klassifizierung von Gebäuden basierend auf Baujahr und Nutzungsart.
"""

from typing import Dict, Optional, Any

class BuildingClassifier:
    """Klasse zur Klassifizierung von Gebäuden nach CEA-Standards."""
    
    def __init__(self):
        """Initialisiert den BuildingClassifier."""
        self.building_periods = {
            "I": (0, 1918),
            "II": (1919, 1948),
            "III": (1949, 1978),
            "IV": (1979, 1994),
            "V": (1995, 2009),
            "VI": (2010, float('inf'))
        }
        
        self.building_types = {
            "MULTI_RES": ["Mehrfamilienhaus", "Wohngebäude", "residential"],
            "SINGLE_RES": ["Einfamilienhaus", "single_family"],
            "OFFICE": ["Bürogebäude", "Verwaltungsgebäude", "office"],
            "INDUSTRIAL": ["Industriegebäude", "Produktionsgebäude", "industrial"],
            "RETAIL": ["Einzelhandel", "Geschäftshaus", "retail"],
            "SCHOOL": ["Schule", "Bildungseinrichtung", "education"],
            "RESTAURANT": ["Restaurant", "Gaststätte", "restaurant"],
            "MULTI_USE": ["Mischnutzung", "mixed_use"],
            "OTHER": ["Sonstiges", "other"]
        }
    
    def get_building_period(self, year: Optional[int]) -> str:
        """
        Ermittelt die Bauperiode basierend auf dem Baujahr.
        
        Args:
            year: Das Baujahr des Gebäudes
            
        Returns:
            Die entsprechende Bauperiode (I-VI)
        """
        if year is None:
            return "III"  # Standardwert für unbekanntes Baujahr
            
        for period, (start, end) in self.building_periods.items():
            if start <= year <= end:
                return period
                
        return "III"  # Fallback wenn kein passendes Intervall gefunden
        
    def get_building_type(self, usage: Optional[str]) -> str:
        """
        Ermittelt den Gebäudetyp basierend auf der Nutzungsart.
        
        Args:
            usage: Die Nutzungsart des Gebäudes
            
        Returns:
            Der entsprechende CEA-Gebäudetyp
        """
        if not usage:
            return "MULTI_RES"  # Standardwert für unbekannte Nutzung
            
        usage = usage.lower()
        for cea_type, keywords in self.building_types.items():
            if any(keyword.lower() in usage for keyword in keywords):
                return cea_type
                
        return "MULTI_RES"  # Fallback wenn keine Übereinstimmung
        
    def get_standard(self, data: Dict[str, Any]) -> str:
        """
        Ermittelt den Gebäudestandard basierend auf Periode und Typ.
        
        Args:
            data: Dictionary mit Gebäudedaten
            
        Returns:
            Der resultierende Gebäudestandard
        """
        # Baujahr extrahieren und konvertieren
        year = None
        if "Gebäudeinfo_BAUJAHR" in data:
            try:
                year = int(data["Gebäudeinfo_BAUJAHR"])
            except (ValueError, TypeError):
                pass
                
        # Nutzung extrahieren
        usage = data.get("Gebäudeinfo_L_NUTZUNG") or data.get("Realnutzung_NUTZUNG_LEVEL1")
        
        # Periode und Typ ermitteln
        period = self.get_building_period(year)
        building_type = self.get_building_type(usage)
        
        # Standard zusammensetzen
        return f"{building_type}_{period}" 
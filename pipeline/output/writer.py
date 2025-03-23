# pipeline/output/writer.py

"""
Output-Writer für die CEA-Pipeline.

Dieses Modul stellt Funktionen zum Speichern der verarbeiteten Daten
in verschiedenen Formaten bereit.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
import geopandas as gpd
import json
import yaml
from core.project_paths import get_output_path

# Logger konfigurieren
logger = logging.getLogger(__name__)

def write_output(data: Dict[str, Any], 
                output_formats: Optional[list] = None,
                output_dir: Optional[Union[str, Path]] = None) -> bool:
    """Speichert die verarbeiteten Daten in den gewünschten Formaten.
    
    Args:
        data: Dictionary mit den zu speichernden Daten
        output_formats: Liste der gewünschten Ausgabeformate (z.B. ['geojson', 'shp', 'csv'])
        output_dir: Optionaler Ausgabepfad (verwendet sonst get_output_path())
        
    Returns:
        bool: True wenn alle Daten erfolgreich gespeichert wurden
    """
    try:
        # Setze Standard-Ausgabeformate wenn keine angegeben
        if output_formats is None:
            output_formats = ['geojson', 'shp']
            
        # Hole Ausgabeverzeichnis
        if output_dir is None:
            output_dir = get_output_path('processed')
        else:
            output_dir = Path(output_dir)
            
        # Stelle sicher dass Verzeichnis existiert
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📝 Speichere Daten in: {output_dir}")
        logger.info(f"📊 Ausgabeformate: {output_formats}")
        
        success = True
        for key, value in data.items():
            if isinstance(value, gpd.GeoDataFrame):
                # Speichere GeoDataFrame in verschiedenen Formaten
                for fmt in output_formats:
                    try:
                        output_path = output_dir / f"{key}.{fmt}"
                        if fmt == 'geojson':
                            value.to_file(output_path, driver='GeoJSON')
                        elif fmt == 'shp':
                            value.to_file(output_path, driver='ESRI Shapefile')
                        elif fmt == 'csv':
                            # Konvertiere Geometrie zu WKT für CSV
                            df_csv = value.copy()
                            df_csv['geometry'] = df_csv['geometry'].apply(lambda x: x.wkt)
                            df_csv.to_csv(output_path, index=False)
                        logger.info(f"✅ {key} als {fmt} gespeichert: {output_path}")
                    except Exception as e:
                        logger.error(f"❌ Fehler beim Speichern von {key} als {fmt}: {str(e)}")
                        success = False
            else:
                # Speichere andere Datentypen als JSON
                try:
                    output_path = output_dir / f"{key}.json"
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(value, f, indent=2, ensure_ascii=False)
                    logger.info(f"✅ {key} als JSON gespeichert: {output_path}")
                except Exception as e:
                    logger.error(f"❌ Fehler beim Speichern von {key} als JSON: {str(e)}")
                    success = False
                    
        return success
        
    except Exception as e:
        logger.error(f"❌ Unerwarteter Fehler beim Speichern der Daten: {str(e)}")
        return False

def write_metadata(metadata: Dict[str, Any], output_dir: Optional[Union[str, Path]] = None) -> bool:
    """Speichert Metadaten zur Verarbeitung.
    
    Args:
        metadata: Dictionary mit Metadaten
        output_dir: Optionaler Ausgabepfad (verwendet sonst get_output_path())
        
    Returns:
        bool: True wenn Metadaten erfolgreich gespeichert wurden
    """
    try:
        # Hole Ausgabeverzeichnis
        if output_dir is None:
            output_dir = get_output_path('metadata')
        else:
            output_dir = Path(output_dir)
            
        # Stelle sicher dass Verzeichnis existiert
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Speichere Metadaten als YAML
        output_path = output_dir / 'processing_metadata.yml'
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True)
            
        logger.info(f"✅ Metadaten gespeichert: {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fehler beim Speichern der Metadaten: {str(e)}")
        return False

import os
from pathlib import Path
from typing import Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import geopandas as gpd
from shapely.geometry import mapping
import json

class SupabaseManager:
    def __init__(self):
        # Pfad zur .env Datei bestimmen
        current_dir = Path(__file__).resolve().parent
        root_dir = current_dir.parent.parent  # Navigiere zum web-Verzeichnis
        env_path = root_dir / '.env'
        
        # .env Datei laden
        if not load_dotenv(env_path):
            raise ValueError("Supabase Umgebungsvariablen nicht gefunden")
            
        # Überprüfen ob die notwendigen Variablen existieren
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_KEY')
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL oder SUPABASE_KEY nicht in .env Datei gefunden")
        self.client: Client = create_client(self.url, self.key)

    def insert_building(self, gml_id: str, geometry: Dict, attributes: Dict[str, Any]) -> Dict:
        """
        Fügt ein neues Gebäude in die buildings Tabelle ein
        """
        building_data = {
            "gml_id": gml_id,
            "geometry": json.dumps(mapping(geometry)),
            "year_of_construction": attributes.get("year_of_construction"),
            "building_type": attributes.get("building_type"),
            "height": attributes.get("height"),
            "storeys": attributes.get("storeys")
        }
        
        result = self.client.table("buildings").insert(building_data).execute()
        return result.data[0] if result.data else None

    def insert_wfs_data(self, building_id: str, data_type: str, attributes: Dict, geometry: Dict) -> Dict:
        """
        Fügt WFS-Daten in die wfs_data Tabelle ein
        """
        wfs_data = {
            "building_id": building_id,
            "data_type": data_type,
            "attributes": attributes,
            "geometry": json.dumps(mapping(geometry))
        }
        
        result = self.client.table("wfs_data").insert(wfs_data).execute()
        return result.data[0] if result.data else None

    def insert_cea_input(self, building_id: str, file_type: str, data: Dict) -> Dict:
        """
        Fügt CEA-Input-Daten in die cea_input_files Tabelle ein
        """
        cea_data = {
            "building_id": building_id,
            "file_type": file_type,
            "data": data
        }
        
        result = self.client.table("cea_input_files").insert(cea_data).execute()
        return result.data[0] if result.data else None

    def get_building_by_gml_id(self, gml_id: str) -> Dict:
        """
        Holt ein Gebäude anhand seiner GML-ID
        """
        result = self.client.table("buildings").select("*").eq("gml_id", gml_id).execute()
        return result.data[0] if result.data else None 
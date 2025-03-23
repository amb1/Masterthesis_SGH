class CEABuildingProcessor:
    def __init__(self, config: dict):
        """Initialisiert den CEA Building Processor.
        
        Args:
            config (dict): Die Konfiguration mit den CEA-Feldern
        """
        self.config = config
        self.cea_fields = config.get('cea_fields', {})
        
    def process_building(self, building: dict) -> dict:
        """Verarbeitet ein einzelnes Gebäude für CEA.
        
        Args:
            building (dict): Die Gebäudeinformationen
            
        Returns:
            dict: Die verarbeiteten Gebäudeinformationen für CEA
        """
        processed = {}
        
        # Verarbeite die Felder für zone.shp
        zone_fields = self.cea_fields.get('zone', {})
        for field, field_type in zone_fields.items():
            if field == 'Name':
                processed[field] = building.get('building_id', '')
            elif field == 'floors_ag':
                processed[field] = building.get('floors_ag', 1)
            elif field == 'floors_bg':
                processed[field] = building.get('floors_bg', 0)
            elif field == 'height_ag':
                processed[field] = building.get('height_ag', 0.0)
            elif field == 'height_bg':
                processed[field] = building.get('height_bg', 0.0)
            elif field == 'REFERENCE':
                processed[field] = building.get('building_id', '')
            elif field == 'house_no':
                processed[field] = building.get('house_no', '')
            elif field == 'street':
                processed[field] = building.get('street', '')
            elif field == 'postcode':
                processed[field] = building.get('postcode', '')
            elif field == 'house_name':
                processed[field] = building.get('house_name', '')
            elif field == 'resi_type':
                processed[field] = building.get('resi_type', '')
            elif field == 'city':
                processed[field] = building.get('city', '')
            elif field == 'country':
                processed[field] = building.get('country', '')
                
        # Verarbeite die Felder für typology.shp
        typology_fields = self.cea_fields.get('typology', {})
        for field, field_type in typology_fields.items():
            if field == 'Name':
                processed[field] = building.get('building_id', '')
            elif field == 'YEAR':
                processed[field] = building.get('year', 2020)
            elif field == 'STANDARD':
                processed[field] = building.get('standard', '')
            elif field == '1ST_USE':
                processed[field] = building.get('1st_use', '')
            elif field == '1ST_USER':
                processed[field] = building.get('1st_user', 1.0)
            elif field == '2ND_USE':
                processed[field] = building.get('2nd_use', '')
            elif field == '2ND_USER':
                processed[field] = building.get('2nd_user', 0.0)
            elif field == '3RD_USE':
                processed[field] = building.get('3rd_use', '')
            elif field == '3RD_USER':
                processed[field] = building.get('3rd_user', 0.0)
            elif field == 'REFERENCE':
                processed[field] = building.get('building_id', '')
                
        return processed 
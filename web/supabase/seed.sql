-- Test-Daten für buildings
INSERT INTO buildings (gml_id, geometry, year_of_construction, building_type, height, storeys)
VALUES 
  ('Building_1', ST_GeomFromText('POINT(13.404954 52.520008)'), 1890, 'Gründerzeit', 20.5, 4),
  ('Building_2', ST_GeomFromText('POINT(13.405954 52.521008)'), 1920, 'Nachkriegszeit', 15.0, 3);

-- Test-Daten für wfs_data
INSERT INTO wfs_data (building_id, data_type, attributes, geometry)
VALUES 
  (1, 'energiebedarf', '{"heizwärmebedarf": 120.5, "warmwasserbedarf": 30.2}'::jsonb, ST_GeomFromText('POINT(13.404954 52.520008)')),
  (2, 'energiebedarf', '{"heizwärmebedarf": 95.3, "warmwasserbedarf": 28.7}'::jsonb, ST_GeomFromText('POINT(13.405954 52.521008)'));

-- Test-Daten für cea_input_files
INSERT INTO cea_input_files (building_id, file_type, data)
VALUES 
  (1, 'zone', '{"zone_type": "residential", "use_type": "MFH"}'::jsonb),
  (2, 'zone', '{"zone_type": "residential", "use_type": "EFH"}'::jsonb); 
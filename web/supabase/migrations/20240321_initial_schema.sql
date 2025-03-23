-- Enable PostGIS extension if not already enabled
CREATE EXTENSION IF NOT EXISTS postgis;

-- CityGML Buildings table (Haupttabelle)
CREATE TABLE IF NOT EXISTS buildings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gml_id TEXT UNIQUE NOT NULL,
    geometry geometry(POLYGON, 4326),
    year_of_construction INTEGER,
    building_type TEXT,
    height NUMERIC,
    storeys INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- WFS Daten table
CREATE TABLE IF NOT EXISTS wfs_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id UUID REFERENCES buildings(id),
    data_type TEXT NOT NULL,
    attributes JSONB,
    geometry geometry(GEOMETRY, 4326),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- CEA Input Files table
CREATE TABLE IF NOT EXISTS cea_input_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    building_id UUID REFERENCES buildings(id),
    file_type TEXT NOT NULL,
    data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices
CREATE INDEX IF NOT EXISTS idx_buildings_gml_id ON buildings(gml_id);
CREATE INDEX IF NOT EXISTS idx_buildings_geometry ON buildings USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_wfs_data_building_id ON wfs_data(building_id);
CREATE INDEX IF NOT EXISTS idx_wfs_data_geometry ON wfs_data USING GIST(geometry);
CREATE INDEX IF NOT EXISTS idx_cea_input_files_building_id ON cea_input_files(building_id);

-- Trigger für updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_buildings_updated_at
    BEFORE UPDATE ON buildings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_wfs_data_updated_at
    BEFORE UPDATE ON wfs_data
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cea_input_files_updated_at
    BEFORE UPDATE ON cea_input_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 
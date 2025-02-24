/*
  # Add buildings table for 3D data

  1. New Tables
    - `buildings`
      - `id` (uuid, primary key)
      - `project_id` (uuid, references projects)
      - `source_type` (text) - either 'citygml' or 'postgis'
      - `source_file` (text, optional) - reference to CityGML file
      - `geometry` (geometry) - PostGIS geometry
      - `height` (numeric)
      - `properties` (jsonb) - additional building properties
      - `created_at` (timestamptz)
      - `updated_at` (timestamptz)

  2. Security
    - Enable RLS
    - Add policies for project owners
*/

-- Enable PostGIS if not already enabled
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create buildings table
CREATE TABLE IF NOT EXISTS buildings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('citygml', 'postgis')),
  source_file text,
  geometry geometry(GEOMETRYZ, 4326),
  height numeric,
  properties jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create spatial index
CREATE INDEX IF NOT EXISTS buildings_geometry_idx ON buildings USING GIST (geometry);

-- Enable RLS
ALTER TABLE buildings ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can manage buildings for their projects"
  ON buildings
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = buildings.project_id
      AND projects.owner_id = auth.uid()
    )
  );

-- Create updated_at trigger
CREATE TRIGGER update_buildings_updated_at
  BEFORE UPDATE ON buildings
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
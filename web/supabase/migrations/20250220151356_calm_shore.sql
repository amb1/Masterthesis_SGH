/*
  # Initial Schema Setup

  1. Tables
    - projects
      - id (uuid, primary key)
      - name (text)
      - description (text)
      - created_at (timestamp)
      - updated_at (timestamp)
      - owner_id (uuid, foreign key to auth.users)
    
    - wfs_streams
      - id (uuid, primary key)
      - project_id (uuid, foreign key to projects)
      - name (text)
      - url (text)
      - layer_name (text)
      - created_at (timestamp)
      - updated_at (timestamp)

  2. Security
    - Enable RLS on all tables
    - Add policies for project access
    - Add policies for WFS stream access
*/

-- Create projects table
CREATE TABLE IF NOT EXISTS projects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  owner_id uuid REFERENCES auth.users(id) NOT NULL
);

-- Create wfs_streams table
CREATE TABLE IF NOT EXISTS wfs_streams (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id uuid REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  name text NOT NULL,
  url text NOT NULL,
  layer_name text NOT NULL,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Enable RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE wfs_streams ENABLE ROW LEVEL SECURITY;

-- Create policies for projects
CREATE POLICY "Users can create their own projects"
  ON projects
  FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = owner_id);

CREATE POLICY "Users can view their own projects"
  ON projects
  FOR SELECT
  TO authenticated
  USING (auth.uid() = owner_id);

CREATE POLICY "Users can update their own projects"
  ON projects
  FOR UPDATE
  TO authenticated
  USING (auth.uid() = owner_id);

CREATE POLICY "Users can delete their own projects"
  ON projects
  FOR DELETE
  TO authenticated
  USING (auth.uid() = owner_id);

-- Create policies for wfs_streams
CREATE POLICY "Users can manage WFS streams for their projects"
  ON wfs_streams
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects
      WHERE projects.id = wfs_streams.project_id
      AND projects.owner_id = auth.uid()
    )
  );

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
CREATE TRIGGER update_projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_wfs_streams_updated_at
  BEFORE UPDATE ON wfs_streams
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
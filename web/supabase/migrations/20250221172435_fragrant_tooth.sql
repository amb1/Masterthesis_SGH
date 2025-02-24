/*
  # Add source_id column to buildings table

  1. Changes
    - Add source_id column to buildings table for external reference IDs
    - Add unique constraint on project_id, source_type, and source_id
    - Update existing source_type check constraint

  2. Notes
    - source_id is used to track external IDs from data sources (e.g., Vienna WFS)
    - Unique constraint prevents duplicate buildings from the same source
*/

-- Add source_id column
ALTER TABLE buildings 
ADD COLUMN source_id text;

-- Drop existing check constraint
ALTER TABLE buildings 
DROP CONSTRAINT IF EXISTS buildings_source_type_check;

-- Add updated check constraint
ALTER TABLE buildings 
ADD CONSTRAINT buildings_source_type_check 
CHECK (source_type IN ('citygml', 'postgis', 'vienna_wfs'));

-- Add unique constraint
ALTER TABLE buildings 
ADD CONSTRAINT buildings_project_source_unique 
UNIQUE (project_id, source_type, source_id);

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS buildings_source_lookup_idx 
ON buildings (project_id, source_type, source_id);
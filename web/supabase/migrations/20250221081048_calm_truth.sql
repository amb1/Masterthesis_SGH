/*
  # Add WFS Parameters and Metadata

  1. New Columns
    - `wfs_version`: WFS version (e.g., '1.1.0', '2.0.0')
    - `crs`: Coordinate Reference System
    - `feature_types`: Array of available feature types
    - `required_parameters`: JSON object for required parameters (e.g., bbox)
    - `metadata`: JSON object for additional metadata

  2. Changes
    - Add new columns to wfs_streams table
    - Add validation for WFS version
*/

ALTER TABLE wfs_streams
ADD COLUMN wfs_version text NOT NULL DEFAULT '1.1.0',
ADD COLUMN crs text,
ADD COLUMN feature_types text[],
ADD COLUMN required_parameters jsonb DEFAULT '{"bbox": true}'::jsonb,
ADD COLUMN metadata jsonb DEFAULT '{}'::jsonb;

-- Add check constraint for WFS version
ALTER TABLE wfs_streams
ADD CONSTRAINT valid_wfs_version
CHECK (wfs_version IN ('1.0.0', '1.1.0', '2.0.0'));
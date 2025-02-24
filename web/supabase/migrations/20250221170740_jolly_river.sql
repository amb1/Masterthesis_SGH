CREATE OR REPLACE FUNCTION get_buildings_bbox(p_project_id uuid)
RETURNS TABLE (
  west float,
  south float,
  east float,
  north float
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    ST_XMin(bbox)::float as west,
    ST_YMin(bbox)::float as south,
    ST_XMax(bbox)::float as east,
    ST_YMax(bbox)::float as north
  FROM (
    SELECT ST_Extent(geometry::geometry) as bbox
    FROM buildings
    WHERE project_id = p_project_id
  ) as extent;
END;
$$ LANGUAGE plpgsql;
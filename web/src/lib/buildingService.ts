import { supabase } from './supabase';
import { processCityGML } from './citygmlService';

export interface Building {
  id: string;
  geometry: any;
  height: number;
  properties: Record<string, any>;
  source_type: 'citygml' | 'postgis';
}

export async function processCityGMLFile(projectId: string, fileUrl: string) {
  try {
    console.log('Processing CityGML file for project:', projectId);
    const result = await processCityGML(fileUrl);
    
    if (!result.success || !result.data) {
      throw new Error(result.error || 'Failed to process CityGML file');
    }

    console.log(`Inserting ${result.data.buildings.length} buildings into database`);

    // Insert buildings in batches to avoid potential size limits
    const batchSize = 100;
    const buildings = result.data.buildings;
    
    for (let i = 0; i < buildings.length; i += batchSize) {
      const batch = buildings.slice(i, i + batchSize);
      const { error } = await supabase.from('buildings').insert(
        batch.map(building => ({
          project_id: projectId,
          source_type: 'citygml',
          source_file: fileUrl,
          geometry: {
            type: 'GeometryZ',
            coordinates: building.geometry.coordinates,
            crs: {
              type: 'name',
              properties: {
                name: 'EPSG:4326'
              }
            }
          },
          height: building.properties.height,
          properties: {
            floors: building.properties.floors,
            yearBuilt: building.properties.yearBuilt,
            buildingType: building.properties.buildingType,
            groundLevel: building.properties.groundLevel,
            originalId: building.id
          }
        }))
      );

      if (error) {
        console.error('Error inserting buildings batch:', error);
        throw error;
      }
      
      console.log(`Inserted batch of ${batch.length} buildings`);
    }

    return result.data.bounds;
  } catch (error) {
    console.error('Error processing CityGML file:', error);
    throw error;
  }
}

export async function loadBuildingsFromDatabase(projectId: string): Promise<Building[]> {
  const { data, error } = await supabase
    .from('buildings')
    .select('*')
    .eq('project_id', projectId)
    .order('created_at', { ascending: false });

  if (error) throw error;
  return data || [];
}
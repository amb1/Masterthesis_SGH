import { supabase } from './supabase';

interface ViennaBuildingData {
  id: string;
  ogc_fid: number;
  geometry: any;
  height: number;
  year_built?: number;
  building_type?: string;
  address?: string;
  district?: string;
  source_updated?: Date;
}

const VIENNA_WFS_URL = 'https://data.wien.gv.at/daten/geo';
const BUILDING_LAYER = 'ogdwien:BKAOGD';

export async function fetchViennaBuildingsInBBox(bbox: [number, number, number, number]): Promise<ViennaBuildingData[]> {
  try {
    const params = new URLSearchParams({
      service: 'WFS',
      version: '2.0.0',
      request: 'GetFeature',
      typeName: BUILDING_LAYER,
      outputFormat: 'application/json',
      srsName: 'EPSG:4326',
      bbox: bbox.join(',') + ',EPSG:4326'
    });

    const response = await fetch(`${VIENNA_WFS_URL}?${params}`);
    if (!response.ok) {
      throw new Error('Failed to fetch Vienna building data');
    }

    const data = await response.json();
    return data.features.map((feature: any) => ({
      id: feature.id,
      ogc_fid: feature.properties.ogc_fid,
      geometry: feature.geometry,
      height: feature.properties.rel_hoehe || 10,
      year_built: feature.properties.baujahr,
      building_type: feature.properties.nutzung,
      address: feature.properties.adresse,
      district: feature.properties.bezirk,
      source_updated: new Date()
    }));
  } catch (error) {
    console.error('Error fetching Vienna buildings:', error);
    throw error;
  }
}

export async function syncViennaBuildingsToDatabase(
  projectId: string, 
  buildings: ViennaBuildingData[]
): Promise<void> {
  try {
    // Process buildings in batches to avoid request size limits
    const batchSize = 100;
    for (let i = 0; i < buildings.length; i += batchSize) {
      const batch = buildings.slice(i, i + batchSize);
      
      const { error } = await supabase.from('buildings').upsert(
        batch.map(building => ({
          project_id: projectId,
          source_type: 'vienna_wfs',
          source_id: building.ogc_fid.toString(), // Use ogc_fid as source_id
          geometry: building.geometry,
          height: building.height,
          properties: {
            year_built: building.year_built,
            building_type: building.building_type,
            address: building.address,
            district: building.district,
            source_updated: building.source_updated
          }
        })),
        {
          onConflict: 'project_id,source_type,source_id',
          ignoreDuplicates: false
        }
      );

      if (error) {
        console.error('Error syncing buildings batch:', error);
        throw error;
      }
    }
  } catch (error) {
    console.error('Error syncing Vienna buildings:', error);
    throw error;
  }
}

export async function updateViennaBuildings(projectId: string): Promise<void> {
  try {
    // Get existing buildings from database
    const { data: existingBuildings, error: fetchError } = await supabase
      .from('buildings')
      .select('source_id')
      .eq('project_id', projectId)
      .eq('source_type', 'vienna_wfs');

    if (fetchError) throw fetchError;

    // Get bounding box of existing buildings
    const { data: bbox, error: bboxError } = await supabase
      .rpc('get_buildings_bbox', { p_project_id: projectId });

    if (bboxError) throw bboxError;
    
    if (!bbox || !bbox.west) {
      throw new Error('No buildings found to update');
    }

    // Fetch fresh data from Vienna WFS
    const viennaBuildings = await fetchViennaBuildingsInBBox([
      bbox.west,
      bbox.south,
      bbox.east,
      bbox.north
    ]);

    // Sync updated data
    await syncViennaBuildingsToDatabase(projectId, viennaBuildings);
  } catch (error) {
    console.error('Error updating Vienna buildings:', error);
    throw error;
  }
}
import { XMLParser } from 'fast-xml-parser';
import proj4 from 'proj4';

interface CityGMLProcessingResult {
  success: boolean;
  error?: string;
  data?: {
    buildings: any[];
    bounds?: {
      north: number;
      south: number;
      east: number;
      west: number;
    };
    sourceCRS?: string;
  };
}

interface BuildingData {
  id: string;
  properties: {
    height: number;
    floors: number;
    yearBuilt: number;
    buildingType: string;
    [key: string]: any;
  };
  geometry?: {
    type: string;
    coordinates: number[][][];
  };
}

// Register common CRS definitions
proj4.defs('EPSG:31256', '+proj=tmerc +lat_0=0 +lon_0=16.33333333333333 +k=1 +x_0=0 +y_0=-5000000 +ellps=bessel +towgs84=577.326,90.129,463.919,5.137,1.474,5.297,2.4232 +units=m +no_defs');
proj4.defs('EPSG:3857', '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs');

function transformCoordinates(coords: number[], fromCRS: string): number[] {
  try {
    if (fromCRS === 'EPSG:4326') {
      return coords; // Already in WGS84
    }

    // Transform to WGS84 (EPSG:4326)
    const [x, y, z] = coords;
    const [lon, lat] = proj4(fromCRS, 'EPSG:4326', [x, y]);
    return [lon, lat, z || 0];
  } catch (error) {
    console.error('Coordinate transformation error:', error);
    return coords;
  }
}

function extractCRS(cityModel: any): string {
  const defaultCRS = 'EPSG:4326';
  
  try {
    // Check bounded by element
    const boundedBy = cityModel['gml:boundedBy'] || cityModel['boundedBy'];
    if (boundedBy) {
      const envelope = boundedBy['gml:Envelope'] || boundedBy['Envelope'];
      if (envelope?.['@_srsName']) {
        return envelope['@_srsName'].replace('urn:ogc:def:crs:', '').replace('::', ':');
      }
    }

    // Check city model attributes
    if (cityModel['@_srsName']) {
      return cityModel['@_srsName'].replace('urn:ogc:def:crs:', '').replace('::', ':');
    }

    return defaultCRS;
  } catch (error) {
    console.warn('Could not determine CRS, using default:', defaultCRS);
    return defaultCRS;
  }
}

export async function processCityGML(url: string): Promise<CityGMLProcessingResult> {
  try {
    console.log('Processing CityGML from URL:', url);
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error('Failed to fetch CityGML file');
    }

    const gmlContent = await response.text();
    console.log('GML content length:', gmlContent.length);

    const parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: '@_',
      parseAttributeValue: true,
      removeNSPrefix: true,
      isArray: (name) => {
        // Always treat these elements as arrays
        const arrayElements = [
          'cityObjectMember',
          'surfaceMember',
          'triangulatedSurface',
          'exterior',
          'interior',
          'LinearRing',
          'posList',
          'pos'
        ];
        return arrayElements.includes(name);
      }
    });

    const result = parser.parse(gmlContent);
    const cityModel = result['CityModel'] || result['core:CityModel'];
    if (!cityModel) {
      throw new Error('Invalid CityGML: No CityModel found');
    }

    const sourceCRS = extractCRS(cityModel);
    console.log('Source CRS:', sourceCRS);

    const buildings: BuildingData[] = [];
    const bounds = {
      north: -90,
      south: 90,
      east: -180,
      west: 180
    };

    const cityObjects = cityModel['cityObjectMember'] || [];
    console.log('Number of city objects found:', cityObjects.length);

    for (const member of (Array.isArray(cityObjects) ? cityObjects : [cityObjects])) {
      const building = member['Building'] || member['bldg:Building'];
      if (!building) continue;

      try {
        const buildingId = building['@_gml:id'] || building['@_id'];
        console.log('Processing building:', buildingId);

        // Extract ground surfaces
        const groundSurfaces = extractGroundSurfaces(building, sourceCRS, bounds);
        if (groundSurfaces.length === 0) {
          console.warn('No ground surfaces found for building:', buildingId);
          continue;
        }

        // Create building data
        const buildingData: BuildingData = {
          id: buildingId,
          properties: {
            height: extractBuildingHeight(building),
            floors: extractFloors(building),
            yearBuilt: extractYearBuilt(building),
            buildingType: extractBuildingType(building),
            groundLevel: extractGroundLevel(building)
          }
        };

        // Combine all ground surfaces into a MultiPolygon
        buildingData.geometry = {
          type: 'MultiPolygon',
          coordinates: groundSurfaces
        };

        buildings.push(buildingData);
        console.log('Successfully processed building:', buildingId);
      } catch (error) {
        console.warn('Error processing building:', error);
      }
    }

    console.log('Total buildings processed:', buildings.length);
    return {
      success: true,
      data: {
        buildings,
        bounds: bounds.north !== -90 ? bounds : undefined,
        sourceCRS
      }
    };

  } catch (error) {
    console.error('Error processing CityGML:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to process CityGML file'
    };
  }
}

function extractGroundSurfaces(building: any, sourceCRS: string, bounds: any): number[][][] {
  const surfaces: number[][][] = [];

  // Process main building ground surfaces
  const mainSurfaces = extractSurfacesFromElement(building, sourceCRS, bounds);
  surfaces.push(...mainSurfaces);

  // Process building parts
  const buildingParts = building['bldg:BuildingPart'] || building['BuildingPart'] || [];
  (Array.isArray(buildingParts) ? buildingParts : [buildingParts]).forEach(part => {
    if (!part) return;
    const partSurfaces = extractSurfacesFromElement(part, sourceCRS, bounds);
    surfaces.push(...partSurfaces);
  });

  return surfaces;
}

function extractSurfacesFromElement(element: any, sourceCRS: string, bounds: any): number[][][] {
  const surfaces: number[][][] = [];

  // Extract from ground surfaces
  const groundSurfaces = element['bldg:GroundSurface'] || element['GroundSurface'] || [];
  (Array.isArray(groundSurfaces) ? groundSurfaces : [groundSurfaces]).forEach(surface => {
    if (!surface) return;
    const polygon = extractPolygon(surface, sourceCRS, bounds);
    if (polygon) surfaces.push(polygon);
  });

  // If no ground surfaces found, try to extract from solid
  if (surfaces.length === 0) {
    const solid = element['bldg:lod2Solid'] || element['lod2Solid'] || element['bldg:lod1Solid'] || element['lod1Solid'];
    if (solid) {
      const exterior = solid['gml:exterior'] || solid['exterior'];
      if (exterior) {
        const shell = exterior['gml:Shell'] || exterior['Shell'];
        if (shell) {
          const surfaceMembers = shell['gml:surfaceMember'] || shell['surfaceMember'] || [];
          (Array.isArray(surfaceMembers) ? surfaceMembers : [surfaceMembers]).forEach(surface => {
            const polygon = extractPolygon(surface, sourceCRS, bounds);
            if (polygon) surfaces.push(polygon);
          });
        }
      }
    }
  }

  return surfaces;
}

function extractPolygon(surface: any, sourceCRS: string, bounds: any): number[][] | null {
  try {
    const polygon = surface['gml:Polygon'] || surface['Polygon'];
    if (!polygon) return null;

    const exterior = polygon['gml:exterior'] || polygon['exterior'];
    if (!exterior) return null;

    const ring = exterior['gml:LinearRing'] || exterior['LinearRing'];
    if (!ring) return null;

    let coordinates: number[][] = [];
    
    // Try posList first
    const posList = ring['gml:posList'] || ring['posList'];
    if (posList) {
      const coords = typeof posList === 'string' ? posList.trim().split(/\s+/).map(Number) : [];
      for (let i = 0; i < coords.length; i += 3) {
        const transformed = transformCoordinates([coords[i], coords[i + 1], coords[i + 2]], sourceCRS);
        coordinates.push(transformed);
        
        // Update bounds
        bounds.north = Math.max(bounds.north, transformed[1]);
        bounds.south = Math.min(bounds.south, transformed[1]);
        bounds.east = Math.max(bounds.east, transformed[0]);
        bounds.west = Math.min(bounds.west, transformed[0]);
      }
    } else {
      // Try pos array
      const posArray = ring['gml:pos'] || ring['pos'] || [];
      (Array.isArray(posArray) ? posArray : [posArray]).forEach(pos => {
        if (typeof pos === 'string') {
          const coords = pos.trim().split(/\s+/).map(Number);
          const transformed = transformCoordinates(coords, sourceCRS);
          coordinates.push(transformed);
          
          // Update bounds
          bounds.north = Math.max(bounds.north, transformed[1]);
          bounds.south = Math.min(bounds.south, transformed[1]);
          bounds.east = Math.max(bounds.east, transformed[0]);
          bounds.west = Math.min(bounds.west, transformed[0]);
        }
      });
    }

    // Ensure the polygon is closed
    if (coordinates.length > 0 && 
        (coordinates[0][0] !== coordinates[coordinates.length - 1][0] ||
         coordinates[0][1] !== coordinates[coordinates.length - 1][1])) {
      coordinates.push([...coordinates[0]]);
    }

    return coordinates.length > 0 ? coordinates : null;
  } catch (error) {
    console.warn('Error extracting polygon:', error);
    return null;
  }
}

function extractBuildingHeight(building: any): number {
  try {
    // Try different height measurements
    const measuredHeight = parseFloat(building['bldg:measuredHeight'] || building['measuredHeight'] || '0');
    const heightAboveGround = parseFloat(building['bldg:heightAboveGround'] || building['heightAboveGround'] || '0');
    
    // Calculate from bounding box if available
    let boundingBoxHeight = 0;
    const boundedBy = building['gml:boundedBy'] || building['boundedBy'];
    if (boundedBy) {
      const envelope = boundedBy['gml:Envelope'] || boundedBy['Envelope'];
      if (envelope) {
        const lowerCorner = envelope['gml:lowerCorner'] || envelope['lowerCorner'];
        const upperCorner = envelope['gml:upperCorner'] || envelope['upperCorner'];
        if (lowerCorner && upperCorner) {
          const lower = typeof lowerCorner === 'string' ? lowerCorner.split(' ').map(Number) : [0, 0, 0];
          const upper = typeof upperCorner === 'string' ? upperCorner.split(' ').map(Number) : [0, 0, 0];
          boundingBoxHeight = Math.abs(upper[2] - lower[2]);
        }
      }
    }

    return Math.max(measuredHeight, heightAboveGround, boundingBoxHeight, 10);
  } catch (error) {
    console.warn('Error extracting building height:', error);
    return 10; // Default height
  }
}

function extractFloors(building: any): number {
  try {
    const storeys = parseInt(building['bldg:storeysAboveGround'] || building['storeysAboveGround'] || '0', 10);
    return storeys > 0 ? storeys : Math.ceil(extractBuildingHeight(building) / 3);
  } catch (error) {
    console.warn('Error extracting floors:', error);
    return 3; // Default number of floors
  }
}

function extractYearBuilt(building: any): number {
  try {
    const yearBuilt = parseInt(building['bldg:yearOfConstruction'] || building['yearOfConstruction'] || '0', 10);
    return yearBuilt > 0 ? yearBuilt : 2000;
  } catch (error) {
    console.warn('Error extracting year built:', error);
    return 2000; // Default year
  }
}

function extractBuildingType(building: any): string {
  try {
    return building['bldg:function'] || building['function'] || 'UNKNOWN';
  } catch (error) {
    console.warn('Error extracting building type:', error);
    return 'UNKNOWN';
  }
}

function extractGroundLevel(building: any): number {
  try {
    const boundedBy = building['gml:boundedBy'] || building['boundedBy'];
    if (boundedBy) {
      const envelope = boundedBy['gml:Envelope'] || boundedBy['Envelope'];
      if (envelope) {
        const lowerCorner = envelope['gml:lowerCorner'] || envelope['lowerCorner'];
        if (lowerCorner) {
          const coords = typeof lowerCorner === 'string' ? lowerCorner.split(' ').map(Number) : [0, 0, 0];
          return coords[2] || 0;
        }
      }
    }
    return 0;
  } catch (error) {
    console.warn('Error extracting ground level:', error);
    return 0;
  }
}
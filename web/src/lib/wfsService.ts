import { XMLParser } from 'fast-xml-parser';
import proj4 from 'proj4';

interface WFSCapabilities {
  version: string;
  featureTypes: string[];
  defaultCRS?: string;
}

interface WFSFeature {
  id: string;
  properties: Record<string, any>;
  geometry?: any;
}

export async function detectWFSCapabilities(url: string): Promise<WFSCapabilities> {
  try {
    // Add GetCapabilities if not present
    const capabilitiesUrl = new URL(url);
    if (!capabilitiesUrl.searchParams.has('service')) {
      capabilitiesUrl.searchParams.set('service', 'WFS');
    }
    if (!capabilitiesUrl.searchParams.has('request')) {
      capabilitiesUrl.searchParams.set('request', 'GetCapabilities');
    }

    const response = await fetch(capabilitiesUrl.toString());
    if (!response.ok) {
      throw new Error('Failed to fetch WFS capabilities');
    }

    const xml = await response.text();
    const parser = new XMLParser({
      ignoreAttributes: false,
      attributeNamePrefix: '@_',
    });
    const result = parser.parse(xml);

    // Handle different WFS versions
    const wfsCapabilities = result['wfs:WFS_Capabilities'] || result['WFS_Capabilities'];
    if (!wfsCapabilities) {
      throw new Error('Invalid WFS capabilities response');
    }

    // Get version
    const version = wfsCapabilities['@_version'] || '1.1.0';

    // Get feature types
    const featureTypeList = wfsCapabilities['FeatureTypeList'] || {};
    const featureTypes = (featureTypeList['FeatureType'] || [])
      .map((ft: any) => ({
        name: ft.Name || ft.Title,
        crs: ft.DefaultCRS || ft.DefaultSRS || ft.SRS
      }))
      .filter(Boolean);

    return {
      version,
      featureTypes: featureTypes.map(ft => ft.name),
      defaultCRS: featureTypes[0]?.crs
    };
  } catch (error) {
    console.error('Error detecting WFS capabilities:', error);
    throw new Error('Failed to detect WFS capabilities');
  }
}

export async function queryWFSFeatures(
  url: string,
  layerName: string,
  bbox: [number, number, number, number],
  version = '1.1.0'
): Promise<WFSFeature[]> {
  try {
    const queryUrl = new URL(url);
    queryUrl.searchParams.set('service', 'WFS');
    queryUrl.searchParams.set('version', version);
    queryUrl.searchParams.set('request', 'GetFeature');
    queryUrl.searchParams.set('typeName', layerName);
    queryUrl.searchParams.set('outputFormat', 'application/json');
    queryUrl.searchParams.set('bbox', bbox.join(','));

    const response = await fetch(queryUrl.toString());
    if (!response.ok) {
      throw new Error('Failed to fetch WFS features');
    }

    const data = await response.json();
    return data.features.map((feature: any) => ({
      id: feature.id,
      properties: feature.properties,
      geometry: feature.geometry
    }));
  } catch (error) {
    console.error('Error querying WFS features:', error);
    throw new Error('Failed to query WFS features');
  }
}

export function transformCoordinates(coords: number[], fromCRS: string, toCRS = 'EPSG:4326'): number[] {
  try {
    // Register common CRS definitions
    proj4.defs('EPSG:31256', '+proj=tmerc +lat_0=0 +lon_0=16.33333333333333 +k=1 +x_0=0 +y_0=-5000000 +ellps=bessel +towgs84=577.326,90.129,463.919,5.137,1.474,5.297,2.4232 +units=m +no_defs');
    proj4.defs('EPSG:3857', '+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs');

    // Transform coordinates
    const [x, y, z] = coords;
    const [lon, lat] = proj4(fromCRS, toCRS, [x, y]);
    return [lon, lat, z || 0];
  } catch (error) {
    console.error('Coordinate transformation error:', error);
    return coords;
  }
}
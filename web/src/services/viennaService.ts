import proj4 from 'proj4';

// MGI/Austria GK East Definition
proj4.defs("EPSG:31256", "+proj=tmerc +lat_0=0 +lon_0=16.33333333333333 +k=1 +x_0=0 +y_0=-5000000 +ellps=bessel +towgs84=577.326,90.129,463.919,5.137,1.474,5.297,2.4232 +units=m +no_defs");

interface BoundingBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

// Koordinatentransformation von WGS84 zu MGI/Austria GK East
const transformCoordinates = (lon: number, lat: number) => {
  return proj4("EPSG:4326", "EPSG:31256", [lon, lat]);
};

export const fetchViennaWFS = async (bbox: BoundingBox, layer: 'FMZKBKMOGD' | 'GEBAEUDETYPOGD') => {
  const { minLon, minLat, maxLon, maxLat } = bbox;
  
  // Koordinaten transformieren
  const min = transformCoordinates(minLon, minLat);
  const max = transformCoordinates(maxLon, maxLat);

  const params = new URLSearchParams({
    SERVICE: 'WFS',
    VERSION: '1.1.0',
    REQUEST: 'GetFeature',
    TYPENAME: `ogdwien:${layer}`,
    SRSNAME: 'urn:x-ogc:def:crs:EPSG:31256',
    BBOX: `${min.x},${min.y},${max.x},${max.y},urn:x-ogc:def:crs:EPSG:31256`,
    OUTPUTFORMAT: 'application/json'
  });

  try {
    const response = await fetch(
      `https://data.wien.gv.at/daten/geo?${params.toString()}`,
      {
        headers: {
          'Accept': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Fehler beim Laden der ${layer} Daten:`, error);
    throw error;
  }
}; 
import { CesiumMath } from 'cesium';

export const VIENNA_CONFIG = {
  camera: {
    initialPosition: {
      longitude: 16.3287,
      latitude: 48.2082,
      height: 1000
    },
    orientation: {
      heading: 0,
      pitch: -45,
      roll: 0
    },
    defaultView: {
      boundingSphere: {
        radius: 5000
      }
    }
  },
  tileset: {
    position: {
      longitude: 16.3287,
      latitude: 48.2082,
      height: 0
    },
    options: {
      maximumScreenSpaceError: 1,
      maximumMemoryUsage: 1024,
      preloadWhenHidden: true,
      preferLeaves: true,
      debugShowBoundingVolume: true,
      debugWireframe: true
    },
    transform: {
      scale: 1.0,
      heightOffset: 0
    }
  },
  terrain: {
    requestVertexNormals: true,
    requestWaterMask: true
  },
  layers: {
    default: {
      arcGIS: false,
      satellite: true,
      tileset: true
    },
    opacity: {
      arcGIS: 1,
      satellite: 1,
      tileset: 1
    }
  }
} as const;

export const VIENNA_BOUNDS = {
  west: CesiumMath.toRadians(16.2),
  south: CesiumMath.toRadians(48.1),
  east: CesiumMath.toRadians(16.5),
  north: CesiumMath.toRadians(48.3)
};

export const LAYER_URLS = {
  arcGIS: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer',
  tileset: 'https://zfwjygqjtbzjyyyuihfv.supabase.co/storage/v1/object/sign/tiles3d/Vienna%20CityGML%203D-Tile/tileset.json'
} as const; 
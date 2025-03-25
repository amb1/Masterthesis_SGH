import { Cartesian3, HeadingPitchRange, Matrix4 } from 'cesium';

export interface CameraConfig {
  initialPosition: {
    longitude: number;
    latitude: number;
    height: number;
  };
  orientation: {
    heading: number;
    pitch: number;
    roll: number;
  };
  defaultView: {
    boundingSphere: {
      radius: number;
    };
  };
}

export interface TilesetConfig {
  position: {
    longitude: number;
    latitude: number;
    height: number;
  };
  options: {
    maximumScreenSpaceError: number;
    maximumMemoryUsage: number;
    preloadWhenHidden: boolean;
    preferLeaves: boolean;
    debugShowBoundingVolume: boolean;
    debugWireframe: boolean;
  };
  transform: {
    scale: number;
    heightOffset: number;
  };
}

export interface TerrainConfig {
  requestVertexNormals: boolean;
  requestWaterMask: boolean;
}

export interface LayerConfig {
  default: {
    arcGIS: boolean;
    satellite: boolean;
    tileset: boolean;
  };
  opacity: {
    arcGIS: number;
    satellite: number;
    tileset: number;
  };
}

export interface CesiumViewerConfig {
  camera: CameraConfig;
  tileset: TilesetConfig;
  terrain: TerrainConfig;
  layers: LayerConfig;
}

export interface GeographicBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface LayerUrls {
  arcGIS: string;
  tileset: string;
}

export interface CesiumTransforms {
  translation: (position: Cartesian3) => Matrix4;
  rotation: (heading: number, pitch: number, roll: number) => Matrix4;
  scale: (scale: number) => Matrix4;
}

export interface CameraOptions {
  destination: Cartesian3;
  orientation: {
    heading: number;
    pitch: number;
    roll: number;
  };
  duration?: number;
  offset?: HeadingPitchRange;
} 
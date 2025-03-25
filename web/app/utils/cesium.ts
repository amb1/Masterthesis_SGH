import { 
  Cartesian3, 
  Math as CesiumMath,
  Matrix4,
  Matrix3,
  HeadingPitchRange,
  HeadingPitchRoll,
  Transforms,
  Cartographic
} from 'cesium';
import { CameraOptions, GeographicBounds } from '../types/cesium';

export const createTranslationMatrix = (
  longitude: number,
  latitude: number,
  height: number = 0
): Matrix4 => {
  return Matrix4.fromTranslation(
    Cartesian3.fromDegrees(longitude, latitude, height)
  );
};

export const createRotationMatrix = (
  heading: number,
  pitch: number,
  roll: number = 0
): Matrix4 => {
  const headingRadians = CesiumMath.toRadians(heading);
  const pitchRadians = CesiumMath.toRadians(pitch);
  const rollRadians = CesiumMath.toRadians(roll);
  
  // Erstelle die Rotationsmatrix mit Transforms
  const transform = Transforms.eastNorthUpToFixedFrame(
    Cartesian3.fromDegrees(0, 0, 0)
  );
  
  // Erstelle eine HeadingPitchRoll-Instanz
  const hpr = new HeadingPitchRoll(headingRadians, pitchRadians, rollRadians);
  
  // Konvertiere zu Rotationsmatrix
  const rotation = Matrix3.fromHeadingPitchRoll(hpr);
  
  return Matrix4.fromRotationTranslation(rotation, Cartesian3.ZERO);
};

export const createScaleMatrix = (scale: number): Matrix4 => {
  return Matrix4.fromScale(new Cartesian3(scale, scale, scale));
};

export const calculateBoundingSphereRadius = (bounds: GeographicBounds): number => {
  const southwest = Cartographic.fromRadians(bounds.west, bounds.south);
  const northeast = Cartographic.fromRadians(bounds.east, bounds.north);
  const center = new Cartographic(
    (southwest.longitude + northeast.longitude) / 2,
    (southwest.latitude + northeast.latitude) / 2
  );
  
  const radius = Cartesian3.distance(
    Cartographic.toCartesian(southwest),
    Cartographic.toCartesian(northeast)
  ) / 2;

  return radius;
};

export const createCameraOptions = (
  longitude: number,
  latitude: number,
  height: number,
  heading: number = 0,
  pitch: number = -45,
  duration: number = 2
): CameraOptions => {
  return {
    destination: Cartesian3.fromDegrees(longitude, latitude, height),
    orientation: {
      heading: CesiumMath.toRadians(heading),
      pitch: CesiumMath.toRadians(pitch),
      roll: 0
    },
    duration
  };
};

export const createHeadingPitchRange = (
  heading: number,
  pitch: number,
  range: number
): HeadingPitchRange => {
  return new HeadingPitchRange(
    CesiumMath.toRadians(heading),
    CesiumMath.toRadians(pitch),
    range
  );
};

export const getTerrainHeight = async (
  longitude: number,
  latitude: number,
  terrainProvider: any
): Promise<number> => {
  const positions = [Cartographic.fromDegrees(longitude, latitude)];
  const heights = await terrainProvider.readyPromise
    .then(() => terrainProvider.requestHeights(positions));
  return heights[0];
}; 
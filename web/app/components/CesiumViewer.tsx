import React, { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Viewer } from "resium";
import { 
  Ion, 
  ArcGisMapServerImageryProvider, 
  createWorldImageryAsync,
  ImageryLayer,
  Scene,
  Viewer as CesiumViewerInstance,
  ImageryLayerCollection,
  Cartesian3,
  Math as CesiumMath,
  createWorldTerrainAsync,
  HeightReference,
  ClippingPlane,
  ClippingPlaneCollection,
  HeadingPitchRange,
  Matrix4,
  Transforms,
  Cartographic,
  SceneMode,
  Cesium3DTileset,
  Cesium3DTileStyle,
  TerrainProvider,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Cesium3DTileFeature,
  Color,
  Matrix3,
  Quaternion
} from "cesium";
import { X, ArrowLeft, RotateCcw, RotateCw, ArrowUp, ArrowDown, ArrowLeft as ArrowLeftIcon, ArrowRight, ZoomIn, ZoomOut } from 'lucide-react';
import LayerSidebar from './LayerSidebar';

interface CesiumViewerComponentProps {
  token: string;
  enabledLayers: {
    arcGIS: boolean;
    satellite: boolean;
    tileset: boolean;
  };
  layerOpacity: {
    arcGIS: number;
    satellite: number;
    tileset: number;
  };
  showTimeline?: boolean;
  tilesetUrl?: string;
  onHomeClick?: () => void;
  onZoomToTileset?: (zoomFn: () => void) => void;
  projectId: string;
  onBack?: () => void;
}

export interface CesiumViewerRef {
  loadAsset: (assetId: number) => Promise<void>;
}

interface FeatureInfo {
  id?: string;
  properties: Record<string, any>;
  tileset?: Cesium3DTileset;
}

const CesiumViewerComponent = forwardRef<CesiumViewerRef, CesiumViewerComponentProps>(({ 
  token,
  enabledLayers,
  layerOpacity,
  showTimeline,
  tilesetUrl,
  onHomeClick,
  onZoomToTileset,
  projectId,
  onBack
}, ref) => {
  const [viewer, setViewer] = useState<CesiumViewerInstance | null>(null);
  const [terrainProvider, setTerrainProvider] = useState<TerrainProvider | null>(null);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<FeatureInfo | null>(null);
  const [currentTileset, setCurrentTileset] = useState<Cesium3DTileset | null>(null);
  const [transformControls, setTransformControls] = useState({
    heading: 0,
    pitch: 0,
    roll: 0,
    scale: 1,
    position: { x: 0, y: 0, z: 0 }
  });
  const [transformMode, setTransformMode] = useState<'position' | 'transform'>('position');
  const [searchAddress, setSearchAddress] = useState('');
  const [currentPosition, setCurrentPosition] = useState({
    longitude: 0,
    latitude: 0,
    height: 0
  });

  useImperativeHandle(ref, () => ({
    loadAsset: async (assetId: number) => {
      if (!viewer) return;
      await loadAsset(assetId);
    }
  }));

  // Terrain Provider initialisieren
  useEffect(() => {
    const initTerrainProvider = async () => {
      try {
        const terrain = await createWorldTerrainAsync({
          requestVertexNormals: true,
          requestWaterMask: true
        });
        setTerrainProvider(terrain);
      } catch (err) {
        console.error('Fehler beim Initialisieren des Terrain Providers:', err);
      }
    };
    initTerrainProvider();
  }, []);

  const highlightFeature = useCallback((feature: Cesium3DTileFeature | null, tileset: Cesium3DTileset) => {
    if (!tileset) return;

    // Standardstil für alle Features
    const defaultStyle = new Cesium3DTileStyle({
      color: 'color("white")',
      show: true
    });

    if (!feature) {
      tileset.style = defaultStyle;
      return;
    }

    try {
      // Versuche verschiedene Identifikatoren für das Feature
      const featureId = feature.getProperty('id') || 
                       feature.getProperty('gmlid') ||
                       feature.getProperty('fid') ||
                       feature._batchId;
      
      // Stil mit stärkerer Hervorhebung für das ausgewählte Feature
      const highlightStyle = new Cesium3DTileStyle({
        color: {
          conditions: [
            [`\${id} === '${featureId}' || \${gmlid} === '${featureId}' || \${fid} === '${featureId}' || \${batchId} === ${feature._batchId}`, 
             'color("yellow", 1.0)'],
            ['true', 'color("white", 1.0)']
          ]
        }
      });

      tileset.style = highlightStyle;
    } catch (err) {
      console.error('Fehler beim Hervorheben des Features:', err);
    }
  }, []);

  const handleFeatureClick = useCallback((movement: any) => {
    if (!viewer || !currentTileset) return;

    const scene = viewer.scene;
    const pickedObject = scene.pick(movement.position);

    if (pickedObject instanceof Cesium3DTileFeature) {
      const properties: Record<string, any> = {};
      
      // Versuche alle verfügbaren Properties zu sammeln
      const availableProps = pickedObject.getPropertyNames?.() || [];
      availableProps.forEach(prop => {
        const value = pickedObject.getProperty(prop);
        if (value !== undefined) {
          properties[prop] = value;
        }
      });

      // Basis-Informationen hinzufügen
      properties['Batch ID'] = pickedObject._batchId;
      if (currentTileset.asset?.id) {
        properties['Tileset ID'] = currentTileset.asset.id;
      }
      
      // Geometrische Eigenschaften extrahieren
      if (pickedObject._content?.boundingSphere) {
        const boundingSphere = pickedObject._content.boundingSphere;
        properties['Position'] = {
          x: boundingSphere.center.x.toFixed(2),
          y: boundingSphere.center.y.toFixed(2),
          z: boundingSphere.center.z.toFixed(2)
        };
        properties['Größe'] = boundingSphere.radius.toFixed(2);
      }

      setSelectedFeature({
        id: properties.id || properties.gmlid || properties.fid || pickedObject._batchId?.toString(),
        properties,
        tileset: currentTileset
      });

      highlightFeature(pickedObject, currentTileset);

      // Kamera auf das Feature zentrieren
      if (pickedObject._content?.boundingSphere) {
        viewer.camera.viewBoundingSphere(
          pickedObject._content.boundingSphere,
          new HeadingPitchRange(0, -0.5, pickedObject._content.boundingSphere.radius * 2)
        );
      }
    } else {
      setSelectedFeature(null);
      if (currentTileset) {
        highlightFeature(null, currentTileset);
      }
    }
  }, [viewer, currentTileset, highlightFeature]);

  useEffect(() => {
    if (!viewer || !currentTileset) return;

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);
    
    handler.setInputAction(handleFeatureClick, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      if (handler && !handler.isDestroyed()) {
        handler.destroy();
      }
    };
  }, [viewer, currentTileset, handleFeatureClick]);

  useEffect(() => {
    if (!terrainProvider) return;

    Ion.defaultAccessToken = token;

    const cesiumViewer = new CesiumViewerInstance('cesiumContainer', {
      terrainProvider,
      baseLayerPicker: true,
      timeline: showTimeline,
      animation: showTimeline,
      geocoder: false,
      infoBox: false,
      selectionIndicator: false
    });

    cesiumViewer.scene.globe.enableLighting = true;

    setViewer(cesiumViewer);

    return () => {
      if (cesiumViewer && !cesiumViewer.isDestroyed()) {
        cesiumViewer.destroy();
      }
    };
  }, [token, terrainProvider, showTimeline]);

  const loadAsset = async (assetId: number) => {
    if (!viewer) return;

    try {
      setLoadingAssets(true);
      setError(null);

      // Vorheriges Tileset entfernen
      if (currentTileset) {
        viewer.scene.primitives.remove(currentTileset);
      }

      const tileset = await Cesium3DTileset.fromIonAssetId(assetId);
      viewer.scene.primitives.add(tileset);
      setCurrentTileset(tileset);

      await viewer.zoomTo(tileset, new HeadingPitchRange(0, -0.5, 0));

      const extras = tileset.asset.extras;
      if (extras?.ion?.defaultStyle) {
        tileset.style = new Cesium3DTileStyle(extras.ion.defaultStyle);
      }

    } catch (err) {
      console.error('Fehler beim Laden des Assets:', err);
      setError(`Fehler beim Laden von Asset ${assetId}: ${err.message}`);
    } finally {
      setLoadingAssets(false);
    }
  };

  const handleBackToProject = () => {
    if (onBack) {
      onBack();
    } else {
      window.history.back();
    }
  };

  const updateTilesetTransform = useCallback(() => {
    if (!currentTileset) return;

    // Erstelle die Rotationsmatrix aus Heading, Pitch und Roll
    const headingRotation = Matrix3.fromRotationZ(CesiumMath.toRadians(transformControls.heading));
    const pitchRotation = Matrix3.fromRotationX(CesiumMath.toRadians(transformControls.pitch));
    const rollRotation = Matrix3.fromRotationY(CesiumMath.toRadians(transformControls.roll));

    // Kombiniere die Rotationen
    const rotation = Matrix3.multiply(
      Matrix3.multiply(headingRotation, pitchRotation, new Matrix3()),
      rollRotation,
      new Matrix3()
    );

    // Erstelle die Transformationsmatrix
    const transform = Matrix4.fromRotationTranslation(
      rotation,
      new Cartesian3(
        transformControls.position.x,
        transformControls.position.y,
        transformControls.position.z
      )
    );

    // Skalierung anwenden
    const scale = Matrix4.fromScale(
      new Cartesian3(
        transformControls.scale,
        transformControls.scale,
        transformControls.scale
      )
    );

    // Kombiniere Transformation und Skalierung
    const finalTransform = Matrix4.multiply(transform, scale, new Matrix4());

    // Wende die Transformation auf das Tileset an
    currentTileset.modelMatrix = finalTransform;
  }, [currentTileset, transformControls]);

  const handleTransformChange = useCallback((type: string, value: number) => {
    setTransformControls(prev => ({
      ...prev,
      [type]: value
    }));
  }, []);

  const handleTransformReset = useCallback(() => {
    setTransformControls({
      heading: 0,
      pitch: 0,
      roll: 0,
      scale: 1,
      position: { x: 0, y: 0, z: 0 }
    });
  }, []);

  useEffect(() => {
    updateTilesetTransform();
  }, [transformControls, updateTilesetTransform]);

  const handleSearchAddress = async () => {
    if (!viewer || !searchAddress) return;
    
    try {
      // Hier würde die Geocoding-Logik kommen
      // Für jetzt setzen wir nur die Position
      const cartographic = Cartographic.fromDegrees(
        currentPosition.longitude,
        currentPosition.latitude,
        currentPosition.height
      );
      
      if (currentTileset) {
        const transform = Transforms.eastNorthUpToFixedFrame(
          Cartesian3.fromRadians(
            cartographic.longitude,
            cartographic.latitude,
            cartographic.height
          )
        );
        currentTileset.modelMatrix = transform;
      }
    } catch (err) {
      console.error('Fehler bei der Adresssuche:', err);
    }
  };

  const handleClickPosition = useCallback((movement: any) => {
    if (!viewer || !currentTileset) return;

    const scene = viewer.scene;
    const cartesian = scene.camera.pickEllipsoid(
      movement.position,
      scene.globe.ellipsoid
    );

    if (cartesian) {
      const cartographic = Cartographic.fromCartesian(cartesian);
      const longitude = CesiumMath.toDegrees(cartographic.longitude);
      const latitude = CesiumMath.toDegrees(cartographic.latitude);
      const height = cartographic.height;

      setCurrentPosition({ longitude, latitude, height });

      const transform = Transforms.eastNorthUpToFixedFrame(
        Cartesian3.fromDegrees(longitude, latitude, height)
      );
      currentTileset.modelMatrix = transform;
    }
  }, [viewer, currentTileset]);

  return (
    <div className="relative w-full h-full">
      <div id="cesiumContainer" className="w-full h-full" />
      
      {/* Zurück-Button */}
      <button
        onClick={onBack}
        className="absolute top-4 left-4 bg-white p-2 rounded shadow-lg hover:bg-gray-100 z-50 flex items-center gap-2"
        title="Zurück zum Projekt"
      >
        <ArrowLeft size={20} />
        <span>Zurück zum Projekt</span>
      </button>

      {/* Layer Sidebar */}
      <LayerSidebar
        onClose={() => {/* handle close */}}
        onLoadAsset={loadAsset}
        enabledLayers={enabledLayers}
        layerOpacity={layerOpacity}
        onLayerToggle={onLayerToggle}
        onOpacityChange={onOpacityChange}
        onZoomToTileset={onZoomToTileset}
        transformControls={transformControls}
        onTransformChange={handleTransformChange}
        onTransformReset={handleTransformReset}
      />

      {/* Loading und Error Anzeige */}
      {loadingAssets && (
        <div className="absolute top-4 right-4 bg-white p-2 rounded shadow">
          Lade Asset...
        </div>
      )}
      {error && (
        <div className="absolute top-4 right-4 bg-red-100 p-2 rounded shadow">
          {error}
        </div>
      )}

      {/* Feature Info Box */}
      {selectedFeature && (
        <div className="absolute top-20 left-4 bg-white p-4 rounded shadow-lg max-w-md z-50">
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-lg font-semibold">
              Objekt Details
            </h3>
            <button
              onClick={() => {
                setSelectedFeature(null);
                if (currentTileset) {
                  highlightFeature(null, currentTileset);
                }
              }}
              className="text-gray-500 hover:text-gray-700"
            >
              <X size={20} />
            </button>
          </div>
          <div className="space-y-2">
            {Object.entries(selectedFeature.properties)
              .filter(([key, value]) => 
                value !== undefined && 
                value !== null && 
                value !== '' &&
                typeof value !== 'object'
              )
              .map(([key, value]) => (
                <div key={key} className="flex">
                  <span className="font-medium w-1/3 text-gray-600">
                    {key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')}:
                  </span>
                  <span className="w-2/3">{value}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
});

CesiumViewerComponent.displayName = 'CesiumViewerComponent';

export default CesiumViewerComponent; 
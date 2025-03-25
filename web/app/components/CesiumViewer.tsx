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
  Color
} from "cesium";
import { X, ArrowLeft } from 'lucide-react';

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
      color: 'rgba(255, 255, 255, 0.5)'
    });

    if (!feature) {
      tileset.style = defaultStyle;
      return;
    }

    // Feature ID für die Bedingung
    const featureId = feature.getProperty('id');
    
    // Stil mit Hervorhebung für das ausgewählte Feature
    const highlightStyle = new Cesium3DTileStyle({
      color: {
        conditions: [
          [`\${id} === '${featureId}'`, 'rgba(255, 255, 0, 0.7)'],
          ['true', 'rgba(255, 255, 255, 0.5)']
        ]
      }
    });

    tileset.style = highlightStyle;
  }, []);

  const handleFeatureClick = useCallback((feature: Cesium3DTileFeature, tileset: Cesium3DTileset) => {
    if (!feature || !tileset) return;

    const properties: Record<string, any> = {};
    const propertiesToCheck = [
      'id',
      'name',
      'description',
      'height',
      'width',
      'length',
      'building_height',
      'building_levels',
      'building_type',
      'roof_type',
      'year_of_construction',
      'address'
    ];

    propertiesToCheck.forEach(prop => {
      const value = feature.getProperty(prop);
      if (value !== undefined) {
        properties[prop] = value;
      }
    });

    setSelectedFeature({
      id: feature.getProperty('id'),
      properties,
      tileset
    });

    highlightFeature(feature, tileset);

    // Kamera auf das Feature zentrieren
    if (viewer) {
      const boundingSphere = (feature as any)._content.boundingSphere;
      if (boundingSphere) {
        viewer.camera.viewBoundingSphere(
          boundingSphere,
          new HeadingPitchRange(0, -0.5, boundingSphere.radius * 2)
        );
      }
    }
  }, [viewer, highlightFeature]);

  useEffect(() => {
    if (!viewer || !enabledLayers.tileset) return;

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);

    handler.setInputAction((movement: any) => {
      const pickedFeature = viewer.scene.pick(movement.position);
      
      if (pickedFeature && pickedFeature instanceof Cesium3DTileFeature && currentTileset) {
        handleFeatureClick(pickedFeature, currentTileset);
      } else {
        setSelectedFeature(null);
        if (currentTileset) {
          highlightFeature(null, currentTileset);
        }
      }
    }, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
      if (handler && !handler.isDestroyed()) {
        handler.destroy();
      }
    };
  }, [enabledLayers.tileset, handleFeatureClick, highlightFeature, viewer, currentTileset]);

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

  return (
    <div className="relative w-full h-full">
      <div id="cesiumContainer" className="w-full h-full" />
      
      {/* Zurück zum Projekt Button */}
      <button
        onClick={handleBackToProject}
        className="absolute top-4 left-4 bg-white p-2 rounded shadow-lg hover:bg-gray-100 z-50 flex items-center gap-2"
        title="Zurück zum Projekt"
      >
        <ArrowLeft size={20} />
        <span>Zurück zum Projekt</span>
      </button>
      
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
              {selectedFeature.properties.name || 'Objekt Details'}
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
              .filter(([_, value]) => value !== undefined && value !== null && value !== '')
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
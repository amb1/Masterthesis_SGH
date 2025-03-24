import React, { useRef, useEffect, useState } from 'react';
import { Viewer, ImageryLayer } from "resium";
import { Ion, ArcGisMapServerImageryProvider, IonImageryProvider, createWorldImageryAsync, Viewer as CesiumViewerType } from "cesium";

interface CesiumViewerProps {
  cesiumToken: string;
  enabledLayers: {
    arcGIS: boolean;
    satellite: boolean;
  };
  layerOpacity: {
    arcGIS: number;
    satellite: number;
  };
  showTimeline?: boolean;
  onHomeClick?: () => void;
}

export default function CesiumViewer({ 
  cesiumToken, 
  enabledLayers, 
  layerOpacity, 
  showTimeline = false,
  onHomeClick 
}: CesiumViewerProps) {
  const viewerRef = useRef<CesiumViewerType>(null);
  const [arcGISProvider, setArcGISProvider] = useState<ArcGisMapServerImageryProvider | null>(null);
  const [satelliteProvider, setSatelliteProvider] = useState<IonImageryProvider | null>(null);

  // Setze den Token sofort, bevor Cesium initialisiert wird
  if (cesiumToken) {
    Ion.defaultAccessToken = cesiumToken;
  }

  useEffect(() => {
    if (cesiumToken) {
      Ion.defaultAccessToken = cesiumToken;
    }
  }, [cesiumToken]);

  useEffect(() => {
    if (enabledLayers.arcGIS) {
      const provider = new ArcGisMapServerImageryProvider({
        baseUrl: "https://services.arcgisonline.com/arcgis/rest/services/World_Street_Map/MapServer",
        enablePickFeatures: false
      });
      setArcGISProvider(provider);
    }
  }, [enabledLayers.arcGIS]);

  useEffect(() => {
    if (enabledLayers.satellite) {
      createWorldImageryAsync().then(provider => {
        setSatelliteProvider(provider);
      });
    }
  }, [enabledLayers.satellite]);

  if (!cesiumToken) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-red-500">Bitte geben Sie einen Cesium Token ein</p>
      </div>
    );
  }

  const handleHomeClick = () => {
    if (viewerRef.current) {
      viewerRef.current.camera.flyHome();
    }
    if (onHomeClick) {
      onHomeClick();
    }
  };

  return (
    <div className="w-full h-full">
      <Viewer 
        full
        ref={viewerRef}
        baseLayerPicker={false}
        timeline={showTimeline}
        animation={showTimeline}
        homeButton={false}
        geocoder={false}
        navigationHelpButton={false}
        sceneModePicker={false}
        fullscreenButton={false}
        infoBox={false}
        selectionIndicator={false}
        navigationInstructionsInitiallyVisible={false}
      >
        {/* ArcGIS Layer */}
        {enabledLayers.arcGIS && arcGISProvider && (
          <ImageryLayer
            imageryProvider={arcGISProvider}
            alpha={layerOpacity.arcGIS}
          />
        )}
        
        {/* Satelliten Layer */}
        {enabledLayers.satellite && satelliteProvider && (
          <ImageryLayer
            imageryProvider={satelliteProvider}
            alpha={layerOpacity.satellite}
          />
        )}
      </Viewer>
    </div>
  );
} 
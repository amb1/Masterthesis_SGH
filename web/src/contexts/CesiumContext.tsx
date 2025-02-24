import React, { createContext, useContext, useEffect, useState, useRef } from 'react';
import * as Cesium from 'cesium';
import "cesium/Build/Cesium/Widgets/widgets.css";

interface CesiumContextType {
  viewer: Cesium.Viewer | null;
  isReady: boolean;
  containerRef: React.RefObject<HTMLDivElement>;
  flyToLocation: (lon: number, lat: number, height?: number) => void;
  showLayer: (layerId: string, show: boolean) => void;
}

const CesiumContext = createContext<CesiumContextType | null>(null);

function useCesium() {
  const context = useContext(CesiumContext);
  if (!context) {
    throw new Error('useCesium must be used within a CesiumProvider');
  }
  return context;
}

interface CesiumProviderProps {
  children: React.ReactNode;
  token: string;
}

function CesiumProvider({ children, token }: CesiumProviderProps) {
  const [isReady, setIsReady] = useState(false);
  const [viewer, setViewer] = useState<Cesium.Viewer | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!token || !containerRef.current) return;

    try {
      Cesium.Ion.defaultAccessToken = token;
      
      const cesiumViewer = new Cesium.Viewer(containerRef.current, {
        terrainProvider: Cesium.createWorldTerrain(),
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        scene3DOnly: true
      });

      setViewer(cesiumViewer);
      setIsReady(true);

      return () => {
        if (cesiumViewer && !cesiumViewer.isDestroyed()) {
          cesiumViewer.destroy();
        }
      };
    } catch (error) {
      console.error('Fehler beim Initialisieren des Cesium Viewers:', error);
    }
  }, [token]);

  const flyToLocation = (lon: number, lat: number, height = 2000) => {
    if (!viewer) return;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, height),
      orientation: {
        heading: 0.0,
        pitch: -Cesium.Math.PI_OVER_FOUR,
        roll: 0.0
      }
    });
  };

  const showLayer = (layerId: string, show: boolean) => {
    if (!viewer) return;
    // Layer-Logik hier implementieren
  };

  return (
    <CesiumContext.Provider value={{
      viewer,
      isReady,
      containerRef,
      flyToLocation,
      showLayer
    }}>
      {children}
    </CesiumContext.Provider>
  );
}

export { CesiumProvider, useCesium }; 
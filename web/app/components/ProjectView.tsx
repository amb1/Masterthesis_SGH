import React, { useState } from 'react';
import { Layers, ArrowLeft, Settings } from 'lucide-react';
import CesiumViewer from './CesiumViewer';
import LayerSidebar from './LayerSidebar';
import ControlsSidebar from './ControlsSidebar';

interface ProjectViewProps {
  projectId: string;
  cesiumToken: string;
  onBack: () => void;
}

export default function ProjectView({ projectId, cesiumToken, onBack }: ProjectViewProps) {
  const [showLayerSidebar, setShowLayerSidebar] = useState(false);
  const [showControlsSidebar, setShowControlsSidebar] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const [enabledLayers, setEnabledLayers] = useState({
    arcGIS: true,
    satellite: false,
  });
  const [layerOpacity, setLayerOpacity] = useState({
    arcGIS: 0.7,
    satellite: 0.7,
  });

  const handleLayerToggle = (layer: keyof typeof enabledLayers) => {
    setEnabledLayers(prev => ({
      ...prev,
      [layer]: !prev[layer]
    }));
  };

  const handleOpacityChange = (layer: keyof typeof layerOpacity, value: number) => {
    setLayerOpacity(prev => ({
      ...prev,
      [layer]: value / 100
    }));
  };

  const handleTimelineToggle = () => {
    setShowTimeline(prev => !prev);
  };

  const handleHomeClick = () => {
    // Diese Funktion wird an CesiumViewer übergeben
  };

  return (
    <div className="relative w-full h-screen">
      {/* Cesium Viewer */}
      <div className="absolute inset-0">
        <CesiumViewer
          cesiumToken={cesiumToken}
          enabledLayers={enabledLayers}
          layerOpacity={layerOpacity}
          showTimeline={showTimeline}
          onHomeClick={handleHomeClick}
        />
      </div>
      
      {/* Navigation Controls */}
      <div className="absolute top-0 left-0 w-full p-4 flex justify-between items-start">
        <div className="flex flex-col gap-2">
          {/* Back Button */}
          <button
            onClick={onBack}
            className="bg-white p-2 rounded-lg shadow-md hover:bg-gray-50 transition-colors flex items-center gap-2 w-fit"
          >
            <ArrowLeft size={20} className="text-blue-500" />
            <span className="text-sm font-medium">Zurück zur Übersicht</span>
          </button>

          {/* Layer Toggle Button */}
          <button
            onClick={() => setShowLayerSidebar(true)}
            className="bg-white p-2 rounded-lg shadow-md hover:bg-gray-50 transition-colors flex items-center gap-2 w-fit"
          >
            <Layers size={20} className="text-blue-500" />
            <span className="text-sm font-medium">Layer</span>
          </button>
        </div>

        {/* Controls Toggle Button */}
        <button
          onClick={() => setShowControlsSidebar(true)}
          className="bg-white p-2 rounded-lg shadow-md hover:bg-gray-50 transition-colors flex items-center gap-2"
        >
          <Settings size={20} className="text-blue-500" />
          <span className="text-sm font-medium">Steuerung</span>
        </button>
      </div>

      {/* Layer Sidebar */}
      {showLayerSidebar && (
        <div className="absolute top-0 left-0 h-full z-40">
          <LayerSidebar
            enabledLayers={enabledLayers}
            layerOpacity={layerOpacity}
            onLayerToggle={handleLayerToggle}
            onOpacityChange={handleOpacityChange}
            onClose={() => setShowLayerSidebar(false)}
          />
        </div>
      )}

      {/* Controls Sidebar */}
      {showControlsSidebar && (
        <div className="absolute top-0 right-0 h-full z-40">
          <ControlsSidebar
            showTimeline={showTimeline}
            onTimelineToggle={handleTimelineToggle}
            onHomeClick={handleHomeClick}
            onClose={() => setShowControlsSidebar(false)}
          />
        </div>
      )}
    </div>
  );
} 
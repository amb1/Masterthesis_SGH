import React from 'react';
import { Layers, X, SlidersHorizontal } from 'lucide-react';

type LayerType = 'arcGIS' | 'satellite';

interface LayerSidebarProps {
  enabledLayers: {
    [K in LayerType]: boolean;
  };
  layerOpacity: {
    [K in LayerType]: number;
  };
  onLayerToggle: (layer: LayerType) => void;
  onOpacityChange: (layer: LayerType, value: number) => void;
  onClose: () => void;
}

export default function LayerSidebar({ 
  enabledLayers, 
  layerOpacity,
  onLayerToggle, 
  onOpacityChange,
  onClose 
}: LayerSidebarProps) {
  return (
    <div className="bg-white w-64 h-full shadow-lg p-4 flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <Layers size={20} className="text-blue-500" />
          <h2 className="text-lg font-semibold">Layer</h2>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      <div className="space-y-6">
        {/* ArcGIS Layer */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabledLayers.arcGIS}
                onChange={() => onLayerToggle('arcGIS')}
                className="w-4 h-4 rounded border-gray-300 text-blue-500 focus:ring-blue-500"
              />
              <span className="font-medium">ArcGIS Karte</span>
            </label>
          </div>
          {enabledLayers.arcGIS && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={16} className="text-gray-500" />
                <span className="text-sm text-gray-600">Transparenz</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={layerOpacity.arcGIS * 100}
                onChange={(e) => onOpacityChange('arcGIS', parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          )}
        </div>

        {/* Satelliten Layer */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabledLayers.satellite}
                onChange={() => onLayerToggle('satellite')}
                className="w-4 h-4 rounded border-gray-300 text-blue-500 focus:ring-blue-500"
              />
              <span className="font-medium">Satellitenbild</span>
            </label>
          </div>
          {enabledLayers.satellite && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <SlidersHorizontal size={16} className="text-gray-500" />
                <span className="text-sm text-gray-600">Transparenz</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={layerOpacity.satellite * 100}
                onChange={(e) => onOpacityChange('satellite', parseInt(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 
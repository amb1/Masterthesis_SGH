import React, { useEffect, useState } from 'react';
import { X, Focus, ChevronDown, ChevronUp, Info, Search, RotateCcw, RotateCw, ArrowUp, ArrowDown, ArrowLeft, ArrowRight, ZoomIn, ZoomOut } from 'lucide-react';
import { Ion } from 'cesium';

type LayerType = 'arcGIS' | 'satellite' | 'tileset';

interface Asset {
  id: number;
  name: string;
  description?: string;
  type: string;
  loaded: boolean;
}

interface LayerSidebarProps {
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
  onLayerToggle: (layer: LayerType) => void;
  onOpacityChange: (layer: LayerType, value: number) => void;
  onClose: () => void;
  onZoomToTileset?: () => void;
  token: string;
  onLoadAsset: (assetId: number) => Promise<void>;
  transformControls?: {
    heading: number;
    pitch: number;
    roll: number;
    scale: number;
    position: { x: number; y: number; z: number };
  };
  onTransformChange?: (type: string, value: number) => void;
  onTransformReset?: () => void;
}

const LayerSidebar: React.FC<LayerSidebarProps> = ({
  enabledLayers,
  layerOpacity,
  onLayerToggle,
  onOpacityChange,
  onClose,
  onZoomToTileset,
  token,
  onLoadAsset,
  transformControls,
  onTransformChange,
  onTransformReset
}) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAssetsOpen, setIsAssetsOpen] = useState(true);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'layers' | 'transform'>('layers');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadAvailableAssets();
  }, [token]);

  const loadAvailableAssets = async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);

      // Ion Token setzen
      Ion.defaultAccessToken = token;

      // Assets von Cesium Ion abrufen
      const response = await fetch('https://api.cesium.com/v1/assets', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      // Assets filtern und formatieren
      const formattedAssets = data.items
        .filter((item: any) => item.type === '3DTILES')
        .map((item: any) => ({
          id: item.id,
          name: item.name,
          description: item.description,
          type: item.type,
          loaded: false
        }));

      setAssets(formattedAssets);
    } catch (err) {
      console.error('Fehler beim Laden der Assets:', err);
      setError('Fehler beim Laden der verfügbaren Assets');
    } finally {
      setLoading(false);
    }
  };

  const handleAssetToggle = async (asset: Asset) => {
    try {
      await onLoadAsset(asset.id);
      
      setAssets(prevAssets => prevAssets.map(a => 
        a.id === asset.id ? { ...a, loaded: !a.loaded } : a
      ));
    } catch (err) {
      console.error('Fehler beim Laden des Assets:', err);
      setError(`Fehler beim Laden von ${asset.name}`);
    }
  };

  return (
    <div className="absolute top-0 right-0 h-full w-80 bg-white shadow-lg z-50 flex flex-col">
      <div className="flex justify-between items-center p-4 border-b">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('layers')}
            className={`px-3 py-1 rounded ${
              activeTab === 'layers' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}
          >
            Layer
          </button>
          {enabledLayers.tileset && (
            <button
              onClick={() => setActiveTab('transform')}
              className={`px-3 py-1 rounded ${
                activeTab === 'transform' ? 'bg-blue-500 text-white' : 'bg-gray-100'
              }`}
            >
              Transform
            </button>
          )}
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
          <X size={20} />
        </button>
      </div>

      {activeTab === 'layers' ? (
        <div className="flex-1 overflow-y-auto p-4">
          {/* Existierende Layer-Steuerung */}
          <div className="space-y-4">
            <div className="space-y-2">
              <h3 className="font-medium">Basiskarten</h3>
              <div className="space-y-4">
                <div>
                  <label className="flex items-center justify-between">
                    <span>ArcGIS</span>
                    <input
                      type="checkbox"
                      checked={enabledLayers.arcGIS}
                      onChange={() => onLayerToggle('arcGIS')}
                      className="ml-2"
                    />
                  </label>
                  {enabledLayers.arcGIS && (
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={layerOpacity.arcGIS}
                      onChange={(e) => onOpacityChange('arcGIS', parseFloat(e.target.value))}
                      className="w-full mt-2"
                    />
                  )}
                </div>
                <div>
                  <label className="flex items-center justify-between">
                    <span>Satellit</span>
                    <input
                      type="checkbox"
                      checked={enabledLayers.satellite}
                      onChange={() => onLayerToggle('satellite')}
                      className="ml-2"
                    />
                  </label>
                  {enabledLayers.satellite && (
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={layerOpacity.satellite}
                      onChange={(e) => onOpacityChange('satellite', parseFloat(e.target.value))}
                      className="w-full mt-2"
                    />
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">3D Modelle</h3>
                <button
                  onClick={() => setIsAssetsOpen(!isAssetsOpen)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  {isAssetsOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
                </button>
              </div>
              {isAssetsOpen && (
                <div className="space-y-4">
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="Assets durchsuchen..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="w-full pl-8 pr-3 py-2 border rounded"
                    />
                    <Search className="absolute left-2 top-2.5 text-gray-400" size={16} />
                  </div>
                  {/* Asset Liste */}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-4">
          {transformControls && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="font-medium">Transformation</h3>
                <button
                  onClick={onTransformReset}
                  className="text-gray-500 hover:text-gray-700"
                  title="Zurücksetzen"
                >
                  <RotateCcw size={20} />
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => onTransformChange?.('heading', transformControls.heading - 5)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach links rotieren"
                >
                  <RotateCcw size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('position', transformControls.position.y + 1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach oben bewegen"
                >
                  <ArrowUp size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('heading', transformControls.heading + 5)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach rechts rotieren"
                >
                  <RotateCw size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('position', transformControls.position.x - 1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach links bewegen"
                >
                  <ArrowLeft size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('scale', transformControls.scale - 0.1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Verkleinern"
                >
                  <ZoomOut size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('position', transformControls.position.x + 1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach rechts bewegen"
                >
                  <ArrowRight size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('position', transformControls.position.y - 1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Nach unten bewegen"
                >
                  <ArrowDown size={20} />
                </button>
                <button
                  onClick={() => onTransformChange?.('scale', transformControls.scale + 0.1)}
                  className="p-2 hover:bg-gray-100 rounded"
                  title="Vergrößern"
                >
                  <ZoomIn size={20} />
                </button>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Rotation</span>
                  <span>{transformControls.heading.toFixed(1)}°</span>
                </div>
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="1"
                  value={transformControls.heading}
                  onChange={(e) => onTransformChange?.('heading', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Skalierung</span>
                  <span>{transformControls.scale.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="10"
                  step="0.1"
                  value={transformControls.scale}
                  onChange={(e) => onTransformChange?.('scale', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default LayerSidebar; 
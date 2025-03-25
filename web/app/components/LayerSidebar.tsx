import React, { useEffect, useState } from 'react';
import { X, Focus, ChevronDown, ChevronUp, Info } from 'lucide-react';
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
}

const LayerSidebar: React.FC<LayerSidebarProps> = ({
  enabledLayers,
  layerOpacity,
  onLayerToggle,
  onOpacityChange,
  onClose,
  onZoomToTileset,
  token,
  onLoadAsset
}) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAssetsOpen, setIsAssetsOpen] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);

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
    <div className="bg-white w-64 h-full shadow-lg p-4 overflow-y-auto">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-lg font-semibold">Layer</h2>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full"
        >
          <X size={20} />
        </button>
      </div>

      <div className="space-y-4">
        {/* Basiskarten */}
        <div className="border-b pb-4">
          <h3 className="font-medium mb-3">Basiskarten</h3>
          
          {/* Satellite Layer */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={enabledLayers.satellite}
                  onChange={() => onLayerToggle('satellite')}
                  className="mr-2"
                />
                <span>Satellit</span>
              </label>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={layerOpacity.satellite}
              onChange={(e) => onOpacityChange('satellite', parseFloat(e.target.value))}
              disabled={!enabledLayers.satellite}
              className="w-full"
            />
          </div>

          {/* ArcGIS Layer */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={enabledLayers.arcGIS}
                  onChange={() => onLayerToggle('arcGIS')}
                  className="mr-2"
                />
                <span>Straßenkarte</span>
              </label>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={layerOpacity.arcGIS}
              onChange={(e) => onOpacityChange('arcGIS', parseFloat(e.target.value))}
              disabled={!enabledLayers.arcGIS}
              className="w-full"
            />
          </div>
        </div>

        {/* 3D Modelle */}
        <div>
          <h3 className="font-medium mb-3">3D Modelle</h3>
          
          {/* 3D Tileset Layer */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center flex-1">
                <input
                  type="checkbox"
                  checked={enabledLayers.tileset}
                  onChange={() => onLayerToggle('tileset')}
                  className="mr-2"
                />
                <span>3D Gebäude</span>
              </label>
              {onZoomToTileset && (
                <button
                  onClick={onZoomToTileset}
                  className="p-1 hover:bg-gray-100 rounded-full ml-2"
                  title="Zum 3D Modell zoomen"
                >
                  <Focus size={18} />
                </button>
              )}
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={layerOpacity.tileset}
              onChange={(e) => onOpacityChange('tileset', parseFloat(e.target.value))}
              disabled={!enabledLayers.tileset}
              className="w-full"
            />
          </div>

          {/* Verfügbare Assets Dropdown */}
          <div className="border rounded-lg overflow-hidden">
            <button
              onClick={() => setIsAssetsOpen(!isAssetsOpen)}
              className="w-full p-3 flex justify-between items-center hover:bg-gray-50"
            >
              <span className="font-medium">Verfügbare Assets</span>
              {isAssetsOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </button>

            {isAssetsOpen && (
              <div className="border-t">
                {loading && (
                  <div className="p-3 text-gray-600">Lade Assets...</div>
                )}

                {error && (
                  <div className="p-3 text-red-500">{error}</div>
                )}

                <div className="divide-y">
                  {assets.map(asset => (
                    <div 
                      key={asset.id}
                      className="p-3 hover:bg-gray-50"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center flex-1">
                          <div className="font-medium">{asset.name}</div>
                          {asset.description && (
                            <div className="relative ml-2">
                              <button
                                onMouseEnter={() => setSelectedAssetId(asset.id)}
                                onMouseLeave={() => setSelectedAssetId(null)}
                                className="text-gray-500 hover:text-gray-700"
                              >
                                <Info size={16} />
                              </button>
                              {selectedAssetId === asset.id && (
                                <div className="absolute z-50 left-0 top-6 w-48 p-2 bg-white border rounded shadow-lg text-sm">
                                  {asset.description}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleAssetToggle(asset)}
                          className={`ml-3 px-2 py-1 rounded text-sm ${
                            asset.loaded 
                              ? 'bg-red-100 text-red-700 hover:bg-red-200'
                              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                          }`}
                        >
                          {asset.loaded ? 'Entfernen' : 'Laden'}
                        </button>
                      </div>
                    </div>
                  ))}

                  {assets.length === 0 && !loading && (
                    <div className="p-3 text-gray-500">
                      Keine 3D Tiles Assets gefunden
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default LayerSidebar; 
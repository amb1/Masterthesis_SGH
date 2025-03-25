import React, { useEffect, useState } from 'react';
import { X, ChevronDown, ChevronUp, Search, Settings, Eye, EyeOff } from 'lucide-react';
import { Ion } from 'cesium';

interface Asset {
  id: number;
  name: string;
  description?: string;
  type: string;
  loaded: boolean;
  selectedProperties?: string[];
  availableProperties?: string[];
  showProperties?: boolean;
}

interface FeatureMetadata {
  building_id?: string;
  name?: string;
  address?: string;
  year_built?: number;
  building_type?: string;
  height?: number;
  floor_area?: number;
  energy_class?: string;
  last_renovation?: string;
  owner?: string;
  custom_properties?: Record<string, any>;
}

interface LayerSidebarProps {
  onClose: () => void;
  token: string;
  onLoadAsset: (assetId: number) => void;
  loadedAssets: number[];
  onUnloadAsset: (assetId: number) => void;
  selectedFeature: FeatureInfo | null;
  onFeaturePropertiesChange: (properties: string[]) => void;
  onSettingsClick?: (assetId: number) => void;
}

const DEFAULT_PROPERTIES = [
  // Allgemeine Eigenschaften
  'id', 'gmlid', 'fid', 'OBJECTID',
  // Geometrische Eigenschaften
  'height', 'Height', 'HOEHE',
  'width', 'Width', 'BREITE',
  'depth', 'Depth', 'TIEFE',
  'area', 'Area', 'FLAECHE',
  'volume', 'Volume', 'VOLUMEN',
  // Gebäudespezifische Eigenschaften
  'type', 'Type', 'GEBAEUDETY',
  'usage', 'Usage', 'NUTZUNG',
  'year', 'Year', 'BAUJAHR',
  'floors', 'Floors', 'GESCHOSSE',
  'address', 'Address', 'ADRESSE',
  'name', 'Name', 'BEZEICHNUNG',
  // IFC-spezifische Eigenschaften
  'IfcClass',
  'IfcType',
  'IfcName',
  'IfcGUID',
  'IfcTag',
  'IfcDescription',
  'IfcMaterial',
  'IfcLayer',
  'IfcCategory',
  'IfcPhase',
  // Energetische Eigenschaften
  'energyClass', 'EnergyClass', 'ENERGIEKL',
  'heatingType', 'HeatingType', 'HEIZUNGSART',
  'insulation', 'Insulation', 'DAEMMUNG',
  // Technische Eigenschaften
  'systemType', 'SystemType', 'SYSTEMTYP',
  'manufacturer', 'Manufacturer', 'HERSTELLER',
  'model', 'Model', 'MODELL',
  'serialNumber', 'SerialNumber', 'SERIENNR'
];

const PROPERTY_CATEGORIES = {
  'Allgemein': ['id', 'gmlid', 'fid', 'OBJECTID'],
  'Geometrie': ['height', 'Height', 'HOEHE', 'width', 'Width', 'BREITE', 'depth', 'Depth', 'TIEFE', 'area', 'Area', 'FLAECHE', 'volume', 'Volume', 'VOLUMEN'],
  'Gebäude': ['type', 'Type', 'GEBAEUDETY', 'usage', 'Usage', 'NUTZUNG', 'year', 'Year', 'BAUJAHR', 'floors', 'Floors', 'GESCHOSSE', 'address', 'Address', 'ADRESSE', 'name', 'Name', 'BEZEICHNUNG'],
  'IFC': ['IfcClass', 'IfcType', 'IfcName', 'IfcGUID', 'IfcTag', 'IfcDescription', 'IfcMaterial', 'IfcLayer', 'IfcCategory', 'IfcPhase'],
  'Energie': ['energyClass', 'EnergyClass', 'ENERGIEKL', 'heatingType', 'HeatingType', 'HEIZUNGSART', 'insulation', 'Insulation', 'DAEMMUNG'],
  'Technik': ['systemType', 'SystemType', 'SYSTEMTYP', 'manufacturer', 'Manufacturer', 'HERSTELLER', 'model', 'Model', 'MODELL', 'serialNumber', 'SerialNumber', 'SERIENNR']
};

const LayerSidebar: React.FC<LayerSidebarProps> = ({
  onClose,
  token,
  onLoadAsset,
  loadedAssets,
  onUnloadAsset,
  selectedFeature,
  onFeaturePropertiesChange,
  onSettingsClick
}) => {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'assets' | 'properties'>('assets');
  const [selectedAssetId, setSelectedAssetId] = useState<number | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>(Object.keys(PROPERTY_CATEGORIES));
  const [showProperties, setShowProperties] = useState<Record<number, boolean>>({});

  // Lade verfügbare Assets
  useEffect(() => {
    loadAvailableAssets();
  }, [token]);

  const loadAvailableAssets = async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);

      Ion.defaultAccessToken = token;

      const response = await fetch('https://api.cesium.com/v1/assets', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const formattedAssets = data.items
        .filter((item: any) => item.type === '3DTILES')
        .map((item: any) => ({
          id: item.id,
          name: item.name,
          description: item.description,
          type: item.type,
          loaded: loadedAssets.includes(item.id),
          selectedProperties: DEFAULT_PROPERTIES,
          availableProperties: DEFAULT_PROPERTIES,
          showProperties: false
        }));

      setAssets(formattedAssets);
    } catch (err) {
      console.error('Fehler beim Laden der Assets:', err);
      setError('Fehler beim Laden der verfügbaren Assets');
    } finally {
      setLoading(false);
    }
  };

  const handleAssetToggle = async (assetId: number) => {
    const asset = assets.find(a => a.id === assetId);
    if (!asset) return;

    if (asset.loaded) {
      onUnloadAsset(assetId);
    } else {
      await onLoadAsset(assetId);
    }

    setAssets(prev => prev.map(a => 
      a.id === assetId ? { ...a, loaded: !a.loaded } : a
    ));
  };

  const handlePropertyToggle = (property: string) => {
    const asset = assets.find(a => a.id === selectedAssetId);
    if (!asset) return;

    const newSelectedProperties = asset.selectedProperties?.includes(property)
      ? asset.selectedProperties.filter(p => p !== property)
      : [...(asset.selectedProperties || []), property];

    setAssets(prev => prev.map(a => 
      a.id === selectedAssetId 
        ? { ...a, selectedProperties: newSelectedProperties }
        : a
    ));

    onFeaturePropertiesChange(newSelectedProperties);
  };

  const handleCategoryToggle = (category: string) => {
    setSelectedCategories(prev => 
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  const toggleProperties = (assetId: number) => {
    setShowProperties(prev => ({
      ...prev,
      [assetId]: !prev[assetId]
    }));
  };

  const handlePropertyChange = (assetId: number, property: string, checked: boolean) => {
    setAssets(prev => prev.map(asset => {
      if (asset.id === assetId) {
        const selectedProps = asset.selectedProperties || [];
        const newProps = checked
          ? [...selectedProps, property]
          : selectedProps.filter(p => p !== property);
        return { ...asset, selectedProperties: newProps };
      }
      return asset;
    }));

    // Aktualisiere die ausgewählten Properties im CesiumViewer
    const asset = assets.find(a => a.id === assetId);
    if (asset) {
      onFeaturePropertiesChange(asset.selectedProperties || []);
    }
  };

  const filteredAssets = assets.filter(asset =>
    asset.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    asset.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="absolute top-0 right-0 h-full w-80 bg-white shadow-lg z-50 flex flex-col">
      <div className="flex justify-between items-center p-4 border-b">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('assets')}
            className={`px-3 py-1 text-sm rounded ${
              activeTab === 'assets' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}
          >
            3D Modelle
          </button>
          <button
            onClick={() => setActiveTab('properties')}
            className={`px-3 py-1 text-sm rounded ${
              activeTab === 'properties' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}
          >
            Eigenschaften
          </button>
        </div>
        <button 
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700"
        >
          <X size={20} />
        </button>
      </div>

      <div className="p-4">
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
          <input
            type="text"
            placeholder="Suchen..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded"
          />
        </div>

        {activeTab === 'assets' ? (
          <div className="space-y-2">
            {filteredAssets.map(asset => (
              <div
                key={asset.id}
                className="flex items-center justify-between p-2 hover:bg-gray-50 rounded"
              >
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${asset.loaded ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span>{asset.name}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAssetToggle(asset.id)}
                    className={`px-2 py-1 text-sm rounded ${
                      asset.loaded ? 'bg-red-100 text-red-600' : 'bg-blue-100 text-blue-600'
                    }`}
                  >
                    {asset.loaded ? 'Entladen' : 'Laden'}
                  </button>
                  {asset.loaded && (
                    <button
                      onClick={() => setSelectedAssetId(asset.id)}
                      className="px-2 py-1 text-sm rounded bg-gray-100 text-gray-600"
                    >
                      Eigenschaften
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(PROPERTY_CATEGORIES).map(([category, properties]) => (
              <div key={category} className="border rounded p-2">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium">{category}</h3>
                  <button
                    onClick={() => handleCategoryToggle(category)}
                    className={`px-2 py-1 text-xs rounded ${
                      selectedCategories.includes(category)
                        ? 'bg-blue-500 text-white'
                        : 'bg-gray-200 text-gray-600'
                    }`}
                  >
                    {selectedCategories.includes(category) ? 'Aktiv' : 'Inaktiv'}
                  </button>
                </div>
                {selectedCategories.includes(category) && (
                  <div className="space-y-1">
                    {properties.map(property => {
                      const asset = assets.find(a => a.id === selectedAssetId);
                      const isSelected = asset?.selectedProperties?.includes(property);
                      
                      return (
                        <div
                          key={property}
                          className="flex items-center justify-between py-1"
                        >
                          <span className="text-sm">{property}</span>
                          <button
                            onClick={() => handlePropertyChange(asset?.id || 0, property, isSelected)}
                            className={`w-4 h-4 rounded ${
                              isSelected ? 'bg-blue-500' : 'bg-gray-200'
                            }`}
                          />
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default LayerSidebar; 
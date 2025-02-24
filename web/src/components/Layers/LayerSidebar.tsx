import { X } from 'lucide-react';
import { Switch } from '@/components/ui/switch';

interface Layer {
  id: string;
  visible: boolean;
}

interface LayerSidebarProps {
  layers: Layer[];
  onToggleLayer: (layerId: string) => void;
  onClose: () => void;
}

export function LayerSidebar({ layers, onToggleLayer, onClose }: LayerSidebarProps) {
  const getLayerName = (id: string) => {
    switch(id) {
      case 'terrain':
        return 'Gelände';
      case 'buildings':
        return 'Gebäude';
      case 'imagery':
        return 'Luftbild';
      default:
        return id;
    }
  };

  return (
    <div className="absolute right-0 top-0 h-full w-64 bg-white shadow-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-semibold">Layer</h3>
        <button 
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded-full"
        >
          ✕
        </button>
      </div>

      <div className="space-y-4">
        {layers.map(layer => (
          <div key={layer.id} className="flex items-center justify-between">
            <label className="text-sm font-medium">
              {getLayerName(layer.id)}
            </label>
            <div className="relative inline-block w-10 mr-2 align-middle select-none">
              <input 
                type="checkbox"
                checked={layer.visible}
                onChange={() => onToggleLayer(layer.id)}
                className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none cursor-pointer"
              />
              <label 
                className="toggle-label block overflow-hidden h-6 rounded-full bg-gray-300 cursor-pointer"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
} 
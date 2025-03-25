import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Layers, ArrowLeft, Settings } from 'lucide-react';
import CesiumViewer from './CesiumViewer';
import LayerSidebar from './LayerSidebar';
import ControlsSidebar from './ControlsSidebar';
import { useNavigate, useParams } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';

interface ProjectViewProps {
  projectId: string;
  cesiumToken: string;
}

const ProjectView: React.FC<ProjectViewProps> = ({ projectId: propProjectId, cesiumToken: propCesiumToken }) => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [projectId, setProjectId] = useState(propProjectId || id || '');
  const [cesiumToken, setCesiumToken] = useState(propCesiumToken);
  const [showLayerSidebar, setShowLayerSidebar] = useState(true);
  const [showControlsSidebar, setShowControlsSidebar] = useState(true);
  const [showTimeline, setShowTimeline] = useState(false);
  const [enabledLayers, setEnabledLayers] = useState({
    arcGIS: false,
    satellite: true,
    tileset: true
  });
  const [layerOpacity, setLayerOpacity] = useState({
    arcGIS: 1,
    satellite: 1,
    tileset: 1
  });
  const [tilesetUrl] = useState("https://zfwjygqjtbzjyyyuihfv.supabase.co/storage/v1/object/sign/tiles3d/Vienna%20CityGML%203D-Tile/tileset.json?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1cmwiOiJ0aWxlczNkL1ZpZW5uYSBDaXR5R01MIDNELVRpbGUvdGlsZXNldC5qc29uIiwiaWF0IjoxNzQyODYxNDM2LCJleHAiOjE3NDM0NjYyMzZ9.QgzGASmdrJbdrsZw6xXma4_aAdYEo7tVYI-q1tCCIuY");
  const [zoomToTilesetFn, setZoomToTilesetFn] = useState<(() => void) | undefined>();
  const viewerRef = useRef<any>(null);

  useEffect(() => {
    const fetchProjectData = async () => {
      if (!projectId) return;

      try {
        const { data, error } = await supabase
          .from('projects')
          .select('*')
          .eq('id', projectId)
          .single();

        if (error) throw error;
        if (data) {
          setCesiumToken(data.cesium_token);
        }
      } catch (error) {
        console.error('Fehler beim Laden der Projektdaten:', error);
      }
    };

    fetchProjectData();
  }, [projectId]);

  const handleLayerToggle = useCallback((layer: keyof typeof enabledLayers) => {
    console.log('Toggle layer:', layer);
    setEnabledLayers(prev => ({
      ...prev,
      [layer]: !prev[layer]
    }));
  }, []);

  const handleOpacityChange = useCallback((layer: keyof typeof layerOpacity, value: number) => {
    console.log('Change opacity:', layer, value);
    setLayerOpacity(prev => ({
      ...prev,
      [layer]: value
    }));
  }, []);

  const handleTimelineToggle = useCallback(() => {
    setShowTimeline(prev => !prev);
  }, []);

  const handleHomeClick = useCallback(() => {
    // Wird für die Home-Button Funktionalität verwendet
  }, []);

  const handleLoadAsset = async (assetId: number) => {
    if (viewerRef.current) {
      await viewerRef.current.loadAsset(assetId);
    }
  };

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  if (!cesiumToken) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {showLayerSidebar && (
        <LayerSidebar
          token={cesiumToken}
          onLoadAsset={handleLoadAsset}
          onClose={() => setShowLayerSidebar(false)}
          enabledLayers={enabledLayers}
          layerOpacity={layerOpacity}
          onLayerToggle={handleLayerToggle}
          onOpacityChange={handleOpacityChange}
          onZoomToTileset={zoomToTilesetFn}
        />
      )}

      <div className="flex-1 relative">
        <CesiumViewer
          ref={viewerRef}
          token={cesiumToken}
          enabledLayers={enabledLayers}
          layerOpacity={layerOpacity}
          showTimeline={showTimeline}
          tilesetUrl={tilesetUrl}
          onHomeClick={handleHomeClick}
          onZoomToTileset={setZoomToTilesetFn}
          projectId={projectId}
          onBack={handleBack}
        />

        {/* Sidebar Toggle Buttons */}
        <div className="absolute top-4 right-4 space-x-2 z-50">
          {!showLayerSidebar && (
            <button
              onClick={() => setShowLayerSidebar(true)}
              className="bg-white p-2 rounded shadow hover:bg-gray-100 flex items-center gap-2"
              title="Layer anzeigen"
            >
              <Layers size={20} />
              <span>Layer anzeigen</span>
            </button>
          )}
          {!showControlsSidebar && (
            <button
              onClick={() => setShowControlsSidebar(true)}
              className="bg-white p-2 rounded shadow hover:bg-gray-100 flex items-center gap-2"
              title="Steuerung anzeigen"
            >
              <Settings size={20} />
              <span>Steuerung anzeigen</span>
            </button>
          )}
        </div>
      </div>

      {showControlsSidebar && (
        <ControlsSidebar
          showTimeline={showTimeline}
          onTimelineToggle={handleTimelineToggle}
          onHomeClick={handleHomeClick}
          onClose={() => setShowControlsSidebar(false)}
        />
      )}
    </div>
  );
};

export default ProjectView; 
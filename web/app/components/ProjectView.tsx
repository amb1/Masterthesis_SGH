import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import CesiumViewer from './CesiumViewer';
import { Settings, Layers } from 'lucide-react';
import { supabase } from '../lib/supabase';

interface ProjectViewProps {
  projectId?: string;
  cesiumToken?: string;
}

const ProjectView: React.FC<ProjectViewProps> = ({ projectId: propProjectId, cesiumToken: propCesiumToken }) => {
  const navigate = useNavigate();
  const { id } = useParams();
  const [projectId] = useState(propProjectId || id || '');
  const [cesiumToken, setCesiumToken] = useState(propCesiumToken || '');
  const [showLayerSidebar, setShowLayerSidebar] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const viewerRef = useRef<any>(null);

  // Token aus der Datenbank laden
  useEffect(() => {
    const loadToken = async () => {
      if (!projectId) return;

      try {
        const { data, error } = await supabase
          .from('projects')
          .select('cesium_token')
          .eq('id', projectId)
          .single();

        if (error) throw error;
        
        if (data?.cesium_token) {
          console.log('Token aus DB geladen:', data.cesium_token);
          setCesiumToken(data.cesium_token);
        } else {
          console.warn('Kein Token in der DB gefunden');
        }
      } catch (err) {
        console.error('Fehler beim Laden des Tokens:', err);
      }
    };

    if (!cesiumToken) {
      loadToken();
    }
  }, [projectId, cesiumToken]);

  const handleBack = useCallback(() => {
    navigate('/');
  }, [navigate]);

  return (
    <div className="flex h-full">
      <div className="flex-1 relative">
        <CesiumViewer
          ref={viewerRef}
          token={cesiumToken}
          projectId={projectId}
          onBack={handleBack}
          showLayerSidebar={showLayerSidebar}
          onToggleLayerSidebar={() => setShowLayerSidebar(!showLayerSidebar)}
          showSettings={showSettings}
          onToggleSettings={() => setShowSettings(!showSettings)}
        />

        {/* Minimierte Steuerelemente */}
        {(!showLayerSidebar || !showSettings) && (
          <div className="absolute top-4 right-4 flex flex-col gap-2 z-50">
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
            {!showSettings && (
              <button
                onClick={() => setShowSettings(true)}
                className="bg-white p-2 rounded shadow hover:bg-gray-100 flex items-center gap-2"
                title="Einstellungen"
              >
                <Settings size={20} />
                <span>Einstellungen</span>
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectView; 
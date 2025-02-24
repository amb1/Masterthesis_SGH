import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ProjectBoundaryEdit } from './ProjectBoundaryEdit';
import { CesiumViewer } from '../Viewer/CesiumViewer';
import { createClient } from '@supabase/supabase-js';
import { X } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { Button } from '../ui/button';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export function ProjectEdit() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [hasBoundary, setHasBoundary] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [cesiumToken, setCesiumToken] = useState<string | null>(null);

  useEffect(() => {
    const loadProject = async () => {
      if (!id) return;

      const { data: project } = await supabase
        .from('projects')
        .select('name, description, cesium_token')
        .eq('id', id)
        .single();
      
      if (project) {
        setName(project.name);
        setDescription(project.description || '');
        setCesiumToken(project.cesium_token);
      }

      const { data: boundary } = await supabase
        .from('project_boundaries')
        .select('*')
        .eq('project_id', id)
        .single();
      
      setHasBoundary(!!boundary);
    };

    loadProject();
  }, [id]);

  const handleSave = async () => {
    if (!id) return;

    try {
      const { error } = await supabase
        .from('projects')
        .update({ name, description })
        .eq('id', id);

      if (error) throw error;
      
      toast.success('Projekt wurde gespeichert');
      navigate(`/project/${id}`);
    } catch (error) {
      toast.error('Fehler beim Speichern des Projekts');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Projekt bearbeiten</h2>
        <div className="flex gap-2">
          <Button 
            variant="secondary" 
            onClick={() => navigate(`/project/${id}`)}
          >
            Abbrechen
          </Button>
          <Button onClick={handleSave}>
            Speichern
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {/* Projektdetails */}
        <div className="border rounded-lg p-6 bg-white space-y-4">
          <h3 className="text-lg font-medium">Projektdetails</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Beschreibung</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Projektgrenzen */}
        <div className="bg-white shadow rounded-lg p-6">
          <ProjectBoundaryEdit 
            projectId={id!}
            onEdit={() => setShowMap(true)}
            onDelete={async () => {
              try {
                await supabase
                  .from('project_boundaries')
                  .delete()
                  .eq('project_id', id);
                setHasBoundary(false);
                toast.success('Projektgrenzen wurden gelöscht');
              } catch (error) {
                console.error('Fehler beim Löschen:', error);
                toast.error('Fehler beim Löschen der Projektgrenzen');
              }
            }}
            hasBoundary={hasBoundary}
            onBoundaryChange={(boundary) => {
              setHasBoundary(!!boundary);
            }}
          />
        </div>
      </div>
      
      {/* CesiumViewer */}
      {showMap && (
        <div className="relative border rounded-lg overflow-hidden" style={{ height: '600px' }}>
          <button 
            onClick={() => setShowMap(false)}
            className="absolute top-2 right-2 z-20 bg-white p-2 rounded-full shadow hover:bg-gray-100"
          >
            <X className="h-4 w-4" />
          </button>
          <CesiumViewer 
            projectId={id!}
            token={cesiumToken!}
          />
        </div>
      )}
    </div>
  );
} 
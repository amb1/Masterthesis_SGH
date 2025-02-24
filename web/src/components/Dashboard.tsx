import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { createClient } from '@supabase/supabase-js';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'react-hot-toast';

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

export function Dashboard() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const { data, error } = await supabase
          .from('projects')
          .select('*')
          .eq('owner_id', session?.user?.id)
          .order('created_at', { ascending: false });

        if (error) throw error;
        setProjects(data || []);
      } catch (error) {
        console.error('Fehler beim Laden der Projekte:', error);
        toast.error('Fehler beim Laden der Projekte');
      }
    };

    if (session?.user) {
      loadProjects();
    }
  }, [session]);

  const handleProjectClick = (projectId: string) => {
    navigate(`/projects/${projectId}`);
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Meine Projekte</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((project) => (
          <div
            key={project.id}
            onClick={() => handleProjectClick(project.id)}
            className="border rounded-lg p-4 cursor-pointer hover:bg-gray-50"
          >
            <h2 className="text-lg font-semibold">{project.name}</h2>
            <p className="text-gray-600 text-sm mt-2">
              Erstellt am: {new Date(project.created_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
} 
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { supabase } from '../lib/supabaseClient';
import { PlusCircle, Map, Edit2, Trash2, ArrowLeft } from 'lucide-react';
import ProjectForm from './ProjectForm';
import ProjectView from './ProjectView';

interface Project {
  id: string;
  name: string;
  description: string;
  cesium_token: string;
  created_at: string;
  updated_at: string;
}

export default function ProjectList() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    if (id && projects.length > 0) {
      const project = projects.find(p => p.id === id);
      if (project) {
        setSelectedProject(project);
      }
    }
  }, [id, projects]);

  async function fetchProjects() {
    try {
      const { data, error } = await supabase
        .from('projects')
        .select('*')
        .order('created_at', { ascending: false });

      if (error) throw error;
      setProjects(data || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(projectId: string) {
    if (!window.confirm('Sind Sie sicher, dass Sie dieses Projekt löschen möchten?')) {
      return;
    }

    try {
      const { error } = await supabase
        .from('projects')
        .delete()
        .eq('id', projectId);

      if (error) throw error;
      await fetchProjects();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function handleEdit(projectId: string) {
    setEditingProjectId(projectId);
    setShowForm(true);
  }

  function handleCloseForm() {
    setShowForm(false);
    setEditingProjectId(null);
  }

  function handleOpenInCesium(project: Project) {
    navigate(`/projects/${project.id}`);
    setSelectedProject(project);
  }

  if (selectedProject) {
    return (
      <div className="h-screen">
        <ProjectView
          projectId={selectedProject.id}
          cesiumToken={selectedProject.cesium_token}
          onBack={() => {
            navigate('/');
            setSelectedProject(null);
          }}
        />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-500 p-4 text-center">
        Fehler beim Laden der Projekte: {error}
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-gray-50">
      {selectedProject ? (
        <div className="h-screen">
          <ProjectView
            projectId={selectedProject.id}
            cesiumToken={selectedProject.cesium_token}
            onBack={() => {
              navigate('/');
              setSelectedProject(null);
            }}
          />
        </div>
      ) : (
        <div className="container mx-auto px-4 py-8">
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-3xl font-bold text-gray-800">Meine Projekte</h1>
            <button
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg flex items-center gap-2 transition-colors"
              onClick={() => setShowForm(true)}
            >
              <PlusCircle size={20} />
              <span>Neues Projekt</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <div
                key={project.id}
                className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow p-6"
              >
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-xl font-semibold text-gray-800">{project.name}</h2>
                  <div className="flex gap-2">
                    <button
                      className="text-gray-600 hover:text-blue-500 transition-colors"
                      onClick={() => handleEdit(project.id)}
                    >
                      <Edit2 size={18} />
                    </button>
                    <button
                      className="text-gray-600 hover:text-red-500 transition-colors"
                      onClick={() => handleDelete(project.id)}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
                
                <p className="text-gray-600 mb-4 line-clamp-2">{project.description || 'Keine Beschreibung verfügbar'}</p>
                
                <div className="flex justify-between items-center">
                  <button
                    className="flex items-center gap-2 text-blue-500 hover:text-blue-600 transition-colors"
                    onClick={() => handleOpenInCesium(project)}
                  >
                    <Map size={18} />
                    <span>In Cesium öffnen</span>
                  </button>
                  <span className="text-sm text-gray-500">
                    Erstellt: {new Date(project.created_at).toLocaleDateString('de-DE')}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {projects.length === 0 && (
            <div className="text-center py-12">
              <p className="text-gray-500 text-lg mb-4">Noch keine Projekte vorhanden</p>
              <button
                className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-lg flex items-center gap-2 mx-auto transition-colors"
                onClick={() => setShowForm(true)}
              >
                <PlusCircle size={24} />
                <span>Erstes Projekt erstellen</span>
              </button>
            </div>
          )}

          {showForm && (
            <ProjectForm
              projectId={editingProjectId || undefined}
              onClose={handleCloseForm}
              onSave={fetchProjects}
            />
          )}
        </div>
      )}
    </main>
  );
} 
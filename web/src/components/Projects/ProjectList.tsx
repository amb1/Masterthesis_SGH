import React, { useEffect, useState } from 'react';
import { Plus, Loader2, FolderPlus } from 'lucide-react';
import { supabase } from '../../lib/supabase';
import { useAuthStore } from '../../store/authStore';
import { useNavigate } from 'react-router-dom';

interface Project {
  id: string;
  name: string;
  description: string;
  created_at: string;
}

export function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showNewProject, setShowNewProject] = useState(false);
  const [newProject, setNewProject] = useState({ name: '', description: '' });
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        if (!user) return;

        const { data, error } = await supabase
          .from('projects')
          .select('*')
          .eq('owner_id', user.id)
          .order('created_at', { ascending: false });

        if (error) throw error;
        setProjects(data || []);
      } catch (error) {
        console.error('Fehler beim Laden der Projekte:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  const handleCreateProject = async () => {
    try {
      if (!user) throw new Error('Nicht authentifiziert');

      const { data, error } = await supabase.from('projects').insert([
        {
          name: newProject.name,
          description: newProject.description,
          owner_id: user.id
        }
      ]).select();

      if (error) throw error;

      setProjects(prev => [...prev, data[0]]);
      setNewProject({ name: '', description: '' });
      setShowNewProject(false);
    } catch (error) {
      console.error('Fehler beim Erstellen des Projekts:', error);
    }
  };

  function handleProjectClick(projectId: string) {
    navigate(`/project/${projectId}`);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Projects</h2>
        <button
          onClick={() => setShowNewProject(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <Plus className="h-5 w-5 mr-2" />
          New Project
        </button>
      </div>

      {showNewProject && (
        <div className="mb-6 bg-white shadow sm:rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg leading-6 font-medium text-gray-900">Create New Project</h3>
            <form onSubmit={handleCreateProject} className="mt-5 space-y-4">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                  Project Name
                </label>
                <input
                  type="text"
                  name="name"
                  id="name"
                  required
                  value={newProject.name}
                  onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                  className="mt-1 block w-full shadow-sm sm:text-sm rounded-md border-gray-300 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                  Description
                </label>
                <textarea
                  id="description"
                  name="description"
                  rows={3}
                  value={newProject.description}
                  onChange={(e) => setNewProject({ ...newProject, description: e.target.value })}
                  className="mt-1 block w-full shadow-sm sm:text-sm rounded-md border-gray-300 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="flex justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setShowNewProject(false)}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="text-center bg-white rounded-lg shadow-sm p-12">
          <FolderPlus className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No projects</h3>
          <p className="mt-1 text-sm text-gray-500">Get started by creating a new project.</p>
          <div className="mt-6">
            <button
              type="button"
              onClick={() => setShowNewProject(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <Plus className="h-5 w-5 mr-2" />
              New Project
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {projects.map((project) => (
              <li
                key={project.id}
                onClick={() => handleProjectClick(project.id)}
                className="px-4 py-4 sm:px-6 hover:bg-gray-50 cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-medium text-blue-600 truncate">{project.name}</h3>
                  <div className="ml-2 flex-shrink-0 flex">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                      Active
                    </span>
                  </div>
                </div>
                <div className="mt-2">
                  <p className="text-sm text-gray-600">{project.description}</p>
                  <p className="mt-2 flex items-center text-sm text-gray-500">
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
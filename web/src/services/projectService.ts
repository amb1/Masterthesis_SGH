import { supabase } from '../lib/supabase';
import type { Project, ProjectBoundary } from '../types/supabase';

export async function getProjectWithBoundary(projectId: string) {
  const { data: project, error: projectError } = await supabase
    .from('projects')
    .select('*')
    .eq('id', projectId)
    .single();

  if (projectError) throw projectError;

  const { data: boundary, error: boundaryError } = await supabase
    .from('project_boundaries')
    .select('*')
    .eq('project_id', projectId)
    .single();

  if (boundaryError && boundaryError.code !== 'PGRST116') {
    throw boundaryError;
  }

  return {
    ...project,
    boundary: boundary || null
  };
}

export async function updateProjectBoundary(
  projectId: string, 
  boundary: Omit<ProjectBoundary, 'id' | 'created_at' | 'updated_at'>
) {
  const { error } = await supabase
    .from('project_boundaries')
    .upsert({
      project_id: projectId,
      ...boundary
    });

  if (error) throw error;
}

export async function deleteProjectBoundary(projectId: string) {
  const { error } = await supabase
    .from('project_boundaries')
    .delete()
    .eq('project_id', projectId);

  if (error) throw error;
} 
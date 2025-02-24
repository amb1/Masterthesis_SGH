import { supabase } from '@/lib/supabase';
import type { Tables } from '@/lib/database.types';

type ProjectBoundary = Tables['project_boundaries']['Row'];

export class BoundaryService {
  static async getBoundary(projectId: string): Promise<ProjectBoundary | null> {
    const { data, error } = await supabase
      .from('project_boundaries')
      .select('*')
      .eq('project_id', projectId)
      .maybeSingle();

    if (error && error.code !== 'PGRST116') throw error;
    return data;
  }

  static async saveBoundary(boundary: Omit<ProjectBoundary, 'id'>): Promise<ProjectBoundary> {
    const { data, error } = await supabase
      .from('project_boundaries')
      .upsert(boundary)
      .select()
      .single();

    if (error) throw error;
    return data;
  }

  static async deleteBoundary(projectId: string) {
    const { error } = await supabase
      .from('project_boundaries')
      .delete()
      .eq('project_id', projectId);

    if (error) throw error;
  }
} 
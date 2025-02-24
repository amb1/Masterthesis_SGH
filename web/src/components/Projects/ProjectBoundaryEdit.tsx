import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { BoundaryService } from '@/services/boundaryService';
import type { Tables } from '@/lib/database.types';
import { toast } from 'react-hot-toast';
import { logger } from '@/utils/logger';

type ProjectBoundary = Tables['project_boundaries']['Row'];

interface ProjectBoundaryEditProps {
  projectId: string;
  onEdit: () => void;
  onDelete?: () => Promise<void>;
  hasBoundary?: boolean;
  onBoundaryChange?: (boundary: ProjectBoundary | null) => void;
}

export function ProjectBoundaryEdit({ 
  projectId, 
  onEdit,
  onDelete,
  hasBoundary,
  onBoundaryChange 
}: ProjectBoundaryEditProps) {
  const [boundary, setBoundary] = useState<ProjectBoundary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadBoundary = async () => {
      try {
        setIsLoading(true);
        const data = await BoundaryService.getBoundary(projectId);
        setBoundary(data);
        if (onBoundaryChange) {
          onBoundaryChange(data);
        }
      } catch (error: any) {
        if (error.code !== 'PGRST116') {
          logger.error('Fehler beim Laden der Projektgrenzen:', error);
          toast.error('Fehler beim Laden der Projektgrenzen');
        }
        setBoundary(null);
        if (onBoundaryChange) {
          onBoundaryChange(null);
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadBoundary();
  }, [projectId, onBoundaryChange]);

  const handleDelete = async () => {
    try {
      await BoundaryService.deleteBoundary(projectId);
      setBoundary(null);
      if (onDelete) {
        await onDelete();
      }
      toast.success('Projektgrenzen wurden gelöscht');
    } catch (error) {
      logger.error('Fehler beim Löschen:', error);
      toast.error('Fehler beim Löschen der Projektgrenzen');
    }
  };

  if (isLoading) {
    return <div>Lade Projektgrenzen...</div>;
  }

  if (!boundary) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-medium">Projektgrenzen</h3>
        <p className="text-sm text-gray-500">Keine Projektgrenzen definiert</p>
        <Button onClick={onEdit}>Projektgrenzen definieren</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium mb-4">Projektgrenzen</h3>
        
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Min. Längengrad</label>
            <div className="p-2 bg-gray-50 rounded">{boundary.min_lon.toFixed(6)}°</div>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Max. Längengrad</label>
            <div className="p-2 bg-gray-50 rounded">{boundary.max_lon.toFixed(6)}°</div>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Min. Breitengrad</label>
            <div className="p-2 bg-gray-50 rounded">{boundary.min_lat.toFixed(6)}°</div>
          </div>
          <div className="space-y-2">
            <label className="text-sm text-gray-600">Max. Breitengrad</label>
            <div className="p-2 bg-gray-50 rounded">{boundary.max_lat.toFixed(6)}°</div>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm text-gray-600">Polygon-Koordinaten</label>
          <div className="p-2 bg-gray-50 rounded text-sm font-mono overflow-x-auto">
            {boundary.polygon.map((coord: number[]) => 
              `[${coord[0].toFixed(6)}, ${coord[1].toFixed(6)}]`
            ).join(', ')}
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={onEdit}>Bearbeiten</Button>
          <Button 
            variant="destructive" 
            onClick={handleDelete}
          >
            Löschen
          </Button>
        </div>
      </div>
    </div>
  );
} 
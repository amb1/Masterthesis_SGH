import React, { useState } from 'react';
import { Upload, X, Loader2 } from 'lucide-react';
import { supabase } from '../../lib/supabase';

interface CityGMLUploadProps {
  onUploadComplete: (modelUrl: string) => void;
}

export function CityGMLUpload({ onUploadComplete }: CityGMLUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.gml')) {
      setError('Please upload a CityGML file (.gml)');
      return;
    }

    try {
      setUploading(true);
      setError(null);
      setProgress(0);

      // Upload to Supabase Storage
      const fileName = `${Date.now()}-${file.name}`;
      const { error: uploadError, data } = await supabase.storage
        .from('citygml')
        .upload(fileName, file, {
          onUploadProgress: (progress) => {
            const percent = (progress.loaded / progress.total) * 100;
            setProgress(Math.round(percent));
          },
        });

      if (uploadError) throw uploadError;

      // Get public URL
      const { data: { publicUrl } } = supabase.storage
        .from('citygml')
        .getPublicUrl(fileName);

      onUploadComplete(publicUrl);
      setProgress(100);
    } catch (error) {
      console.error('Upload error:', error);
      setError(error instanceof Error ? error.message : 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="w-full">
      {error && (
        <div className="mb-4 bg-red-50 p-4 rounded-md flex items-center justify-between">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-center justify-center w-full">
        <label className={`
          w-full flex flex-col items-center px-4 py-6 
          bg-white rounded-lg shadow-sm tracking-wide 
          border-2 border-dashed 
          ${uploading ? 'border-blue-300 bg-blue-50' : 'border-blue-200 hover:border-blue-400'}
          cursor-pointer transition-colors
        `}>
          {uploading ? (
            <div className="text-center">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto" />
              <span className="mt-2 text-sm text-blue-600">
                Uploading... {progress}%
              </span>
            </div>
          ) : (
            <>
              <Upload className="w-8 h-8 text-blue-500" />
              <span className="mt-2 text-base text-gray-700">
                Select CityGML file
              </span>
              <span className="text-xs text-gray-500 mt-1">
                Supported format: .gml
              </span>
            </>
          )}
          <input
            type="file"
            className="hidden"
            accept=".gml"
            onChange={handleFileUpload}
            disabled={uploading}
          />
        </label>
      </div>
    </div>
  );
}
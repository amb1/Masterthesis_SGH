import React, { useState } from 'react';
import { Map, X } from 'lucide-react';
import { CesiumViewer } from '../Viewer/CesiumViewer';

interface ProjectLayoutProps {
  children: React.ReactNode;
}

export function ProjectLayout({ children }: ProjectLayoutProps) {
  const [showMap, setShowMap] = useState(false);

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <div className={`flex-1 overflow-auto transition-all ${showMap ? 'w-1/2' : 'w-full'}`}>
        {children}
      </div>
      
      {!showMap && (
        <button
          onClick={() => setShowMap(true)}
          className="fixed bottom-4 right-4 bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title="Show Map"
        >
          <Map className="h-6 w-6" />
        </button>
      )}

      {showMap && (
        <div className="w-1/2 border-l border-gray-200 bg-white relative">
          <button
            onClick={() => setShowMap(false)}
            className="absolute top-2 right-2 z-10 p-2 bg-white rounded-full shadow-md hover:bg-gray-50"
            title="Close Map"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
          <div className="h-full">
            <CesiumViewer standalone={true} />
          </div>
        </div>
      )}
    </div>
  );
}
import React from 'react';
import { X, Home, Search, Clock, Settings } from 'lucide-react';

interface ControlsSidebarProps {
  showTimeline: boolean;
  onTimelineToggle: () => void;
  onHomeClick: () => void;
  onClose: () => void;
}

export default function ControlsSidebar({
  showTimeline,
  onTimelineToggle,
  onHomeClick,
  onClose
}: ControlsSidebarProps) {
  return (
    <div className="bg-white w-64 h-full shadow-lg p-4 flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <Settings size={20} className="text-blue-500" />
          <h2 className="text-lg font-semibold">Steuerung</h2>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-700 transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      <div className="space-y-4">
        {/* Home Button */}
        <button
          onClick={onHomeClick}
          className="flex items-center gap-3 w-full p-2 hover:bg-gray-50 rounded-lg transition-colors"
        >
          <Home size={20} className="text-blue-500" />
          <span className="font-medium">Zur Startansicht</span>
        </button>

        {/* Timeline Toggle */}
        <button
          onClick={onTimelineToggle}
          className="flex items-center gap-3 w-full p-2 hover:bg-gray-50 rounded-lg transition-colors"
        >
          <Clock size={20} className={showTimeline ? "text-blue-500" : "text-gray-500"} />
          <span className="font-medium">Timeline {showTimeline ? "ausblenden" : "einblenden"}</span>
        </button>

        {/* Geocoder (Adresssuche) */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-2">
            <Search size={16} className="text-gray-500" />
            <span className="text-sm font-medium">Adresssuche</span>
          </div>
          <input
            type="text"
            placeholder="Adresse eingeben..."
            className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
    </div>
  );
} 
import { useState } from 'react';

interface SearchBarProps {
  onSearch: (result: any) => void;
}

export function SearchBar({ onSearch }: SearchBarProps) {
  const [searchTerm, setSearchTerm] = useState('');

  const handleSearch = async () => {
    if (!searchTerm.trim()) return;

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchTerm)}`
      );
      
      const data = await response.json();
      
      if (data && data[0]) {
        onSearch({
          coordinates: {
            lat: parseFloat(data[0].lat),
            lon: parseFloat(data[0].lon)
          },
          display_name: data[0].display_name
        });
      }
    } catch (error) {
      console.error('Fehler bei der Adresssuche:', error);
    }
  };

  return (
    <div className="flex gap-2">
      <input
        type="text"
        placeholder="Adresse suchen..."
        value={searchTerm}
        onChange={(e) => setSearchTerm(e.target.value)}
        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        className="flex-1 px-3 py-2 border rounded-md"
      />
      <button 
        onClick={handleSearch}
        className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
      >
        Suchen
      </button>
    </div>
  );
} 
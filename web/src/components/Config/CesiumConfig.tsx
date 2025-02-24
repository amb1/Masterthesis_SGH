import React, { useState } from 'react';

interface CesiumConfigProps {
  onSave: (token: string) => void;
  onCancel: () => void;
  initialToken?: string;
}

export function CesiumConfig({ onSave, onCancel, initialToken }: CesiumConfigProps) {
  const [token, setToken] = useState(initialToken || '');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (!token.trim()) {
        throw new Error('Token darf nicht leer sein');
      }
      onSave(token);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Ein Fehler ist aufgetreten');
    }
  };

  return (
    <div className="bg-white shadow sm:rounded-lg">
      <div className="px-4 py-5 sm:p-6">
        <h3 className="text-lg leading-6 font-medium text-gray-900">
          Cesium Access Token {initialToken ? 'bearbeiten' : 'erforderlich'}
        </h3>
        <div className="mt-2 max-w-xl text-sm text-gray-500">
          <p>
            Für die 3D-Ansicht benötigen Sie einen Cesium ion Access Token.
            Sie können einen kostenlosen Token erhalten auf{' '}
            <a
              href="https://cesium.com/ion/signup"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-500"
            >
              cesium.com/ion/signup
            </a>
          </p>
        </div>

        {error && (
          <div className="mt-2 text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5">
          <div className="w-full sm:max-w-xs">
            <label htmlFor="token" className="sr-only">
              Cesium Access Token
            </label>
            <input
              type="text"
              id="token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className="shadow-sm focus:ring-blue-500 focus:border-blue-500 block w-full sm:text-sm border-gray-300 rounded-md"
              placeholder="Ihr Cesium Access Token"
            />
          </div>
          <div className="mt-3 flex space-x-3">
            <button
              type="submit"
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Token speichern
            </button>
            <button
              type="button"
              onClick={onCancel}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Abbrechen
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
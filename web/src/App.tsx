import { BrowserRouter } from 'react-router-dom';
import { ErrorBoundary } from './components/ErrorBoundary';
import { CesiumProvider } from './contexts/CesiumContext';
import { AuthProvider } from './contexts/AuthContext';
import { Toaster } from 'react-hot-toast';
import { Routes } from './routes';

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <CesiumProvider token={import.meta.env.VITE_CESIUM_TOKEN}>
            <div className="min-h-screen bg-gray-50">
              <Routes />
              <Toaster position="top-right" />
            </div>
          </CesiumProvider>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
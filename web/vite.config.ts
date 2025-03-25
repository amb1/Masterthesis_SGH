import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import cesium from 'vite-plugin-cesium';
import path from 'path';

export default defineConfig({
  plugins: [react(), cesium()],
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './app')
    }
  },
  envDir: '.',
  build: {
    outDir: 'dist',
    sourcemap: true
  },
  server: {
    port: 5173,
    host: true,
    fs: {
      // Erlaubt den Zugriff auf Cesium-Assets
      allow: ['..']
    }
  }
});
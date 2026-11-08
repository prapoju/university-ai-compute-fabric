import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The console talks to the real FastAPI process on :8000 through the same origin, so no CORS is needed (D-P5).
const api = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': api, '/healthz': api } },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true, proxy: { '/api': api, '/healthz': api } },
});

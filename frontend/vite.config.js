import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The Google Maps key lives in the repo's .env (gitignored) as GOOGLE_MAP_API; only that name and VITE_*
// reach the browser. Without it the map falls back to OpenStreetMap.
export default defineConfig({ plugins: [react(), tailwindcss()], envDir: '..', envPrefix: ['VITE_', 'GOOGLE_MAP_API'] })

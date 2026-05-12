import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const backendTarget = process.env.ROUTEDECK_BACKEND_URL ?? 'http://127.0.0.1:8000'
const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@routedeck/react': path.resolve(__dirname, '../../../react/src'),
    },
  },
  server: {
    proxy: {
      '/manifest': backendTarget,
      '/snapshot': backendTarget,
      '/action': backendTarget,
    },
  },
})

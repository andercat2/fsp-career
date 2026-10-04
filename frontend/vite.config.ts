import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const api = process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000'

// В режиме разработки запросы /api проксируются на бэкенд (по умолчанию 127.0.0.1:8000).
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: api, changeOrigin: true },
      '/docs': { target: api, changeOrigin: true },
      '/openapi.json': { target: api, changeOrigin: true },
    },
  },
  build: { chunkSizeWarningLimit: 1500 },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_PROXY_TARGET = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Lets a single https tunnel (ngrok/cloudflared) on the Vite port serve
    // both the frontend and the bot's aiohttp API without CORS headaches.
    proxy: {
      '/api': { target: API_PROXY_TARGET, changeOrigin: true },
      '/media': { target: API_PROXY_TARGET, changeOrigin: true },
    },
    // Vite blocks requests whose Host header isn't localhost by default.
    // The tunnel subdomain is random on every restart (ngrok/cloudflared),
    // so just allow any host — this only matters for local dev tooling.
    allowedHosts: true,
  },
  preview: {
    proxy: {
      '/api': { target: API_PROXY_TARGET, changeOrigin: true },
      '/media': { target: API_PROXY_TARGET, changeOrigin: true },
    },
    allowedHosts: true,
  },
})

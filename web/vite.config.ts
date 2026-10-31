import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// The app calls the API at relative /api paths; in development Vite proxies them to the local FastAPI.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      port: Number(env.WEB_DEV_PORT || 5173),
      strictPort: true,
      proxy: { '/api': { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true } },
    },
  }
})

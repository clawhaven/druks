import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// Repo-root dist/, where the backend serves the SPA from (app.frontend).
const repoDist = fileURLToPath(
  new URL('../dist/', import.meta.url),
)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // FastAPI serves the API; Vite proxies during dev so the SPA can
      // hit /api/... same-origin without CORS.
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: repoDist,
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Split rarely-changing vendor code out of the main app chunk
        // so re-deploys (which mostly touch app code) don't bust the
        // operator's cache for these. Also keeps the main bundle
        // under the 500 KB warning threshold without raising the
        // limit, which would just hide the signal.
        //
        // Markdown rendering is its own chunk because react-markdown
        // + remark-gfm + their micromark deps pull in a sizable
        // tokenizer that only a few detail pages actually need.
        //
        // Vite 8 / rolldown took the static-map form of ``manualChunks``
        // away; the function form below is the supported equivalent.
        manualChunks(id: string): string | undefined {
          if (id.includes('node_modules/react-markdown') ||
              id.includes('node_modules/remark-') ||
              id.includes('node_modules/micromark') ||
              id.includes('node_modules/mdast-') ||
              id.includes('node_modules/unist-') ||
              id.includes('node_modules/hast-')) {
            return 'markdown-vendor'
          }
          if (id.includes('node_modules/@tanstack/react-query')) {
            return 'query-vendor'
          }
          if (id.includes('node_modules/react') ||
              id.includes('node_modules/scheduler')) {
            return 'react-vendor'
          }
          return undefined
        },
      },
    },
  },
})

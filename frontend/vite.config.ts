import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA({
    registerType: 'autoUpdate',
    includeAssets: ['icon.svg', 'apple-touch-icon-180x180.png'],
    manifest: {
      name: 'Apply Agent', short_name: 'Apply', description: 'Başvuru çalışma alanın',
      display: 'standalone', start_url: '/', scope: '/', lang: 'tr',
      theme_color: '#864b3e', background_color: '#f8f5ef',
      icons: [
        { src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' },
        { src: '/pwa-512x512.png', sizes: '512x512', type: 'image/png' },
        { src: '/maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    workbox: {
      globPatterns: ['**/*.{js,css,html,svg,png,ico,woff2}'],
      navigateFallbackDenylist: [/^\/api\//, /^\/api$/],
      runtimeCaching: [],
    },
  })],
  server: {
    port: 5173,
    proxy: { '/api': {
      target: 'http://127.0.0.1:8000',
      configure(proxy) {
        // Vite otherwise turns an unreachable backend into a generic HTTP 500.
        proxy.on('error', (_error, _request, response) => {
          if ('writeHead' in response && !response.headersSent) {
            response.writeHead(503, { 'X-Apply-Agent-Offline': '1' })
            response.end()
          }
        })
      },
    } },
  },
})

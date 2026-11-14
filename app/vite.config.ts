import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import { writeFileSync, mkdirSync } from 'node:fs'

// identificador deste build: vai para o app (__BUILD_ID__) e para dist/versao.json; o app compara os dois e oferece Atualizar
const BUILD_ID = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    { name: 'gs-versao', closeBundle() { mkdirSync('dist', { recursive: true }); writeFileSync('dist/versao.json', JSON.stringify({ build: BUILD_ID, quando: new Date().toISOString() })) } },
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: false,
      includeAssets: ['icone-192.png', 'icone-512.png', 'push-sw.js'],
      manifest: {
        name: 'Editor GS',
        short_name: 'Editor GS',
        description: 'Edição de vídeo por conversa da Grava Simples',
        lang: 'pt-BR',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: '#000921',
        theme_color: '#000921',
        icons: [
          { src: '/icone-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icone-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
        share_target: {
          action: '/compartilhar',
          method: 'POST',
          enctype: 'multipart/form-data',
          params: {
            title: 'title', text: 'text', url: 'url',
            files: [{ name: 'arquivos', accept: ['video/*', 'audio/*', 'image/*', '.mp4', '.mov', '.m4a', '.mp3', '.wav'] }],
          },
        },
      },
      workbox: { importScripts: ['push-sw.js'], navigateFallback: '/index.html', navigateFallbackDenylist: [/^\/editor/, /^\/compartilhar/, /^\/api\//, /^\/arquivos\//, /^\/entrar/], globPatterns: ['**/*.{js,css,html,png,svg,woff2}'], maximumFileSizeToCacheInBytes: 6_000_000,
        runtimeCaching: [{ urlPattern: /^\/api\//, handler: 'NetworkOnly' }, { urlPattern: /^\/arquivos\//, handler: 'NetworkOnly' }] },
    }),
  ],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:3200', '/arquivos': 'http://127.0.0.1:3200' } },
  build: { outDir: 'dist' },
  define: { __BUILD_ID__: JSON.stringify(BUILD_ID) },
})

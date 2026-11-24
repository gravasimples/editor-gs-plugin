// Editor manual (12/11/2026): segundo pacote, com raiz em remotion/editor. Os imports resolvem a partir de remotion/node_modules (React 19,
// remotion, @remotion/player, gsap), o mesmo motor do render; sai em app/dist/editor e o gateway serve em /editor/.
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

const raiz = fileURLToPath(new URL('../remotion/editor', import.meta.url))
export default defineConfig({
  root: raiz,
  base: '/editor/',
  plugins: [react()],
  build: { outDir: fileURLToPath(new URL('./dist/editor', import.meta.url)), emptyOutDir: true, chunkSizeWarningLimit: 2000 },
})

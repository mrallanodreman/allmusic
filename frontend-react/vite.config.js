import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Canonical público: https://mfmood.com/ (root). El backend mantiene
  // /allmusic/* como alias legacy para no romper enlaces antiguos.
  base: '/',
  // Los PNG viven una sola vez en public/ (raíz del repo) y se copian al build.
  publicDir: '../public',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    proxy: {
      '/radio': 'http://127.0.0.1:2426',
      '/status': 'http://127.0.0.1:2426',
      // Mismo buscador y reproductor usados por AllMusic clásico.
      '/search': 'http://127.0.0.1:2426',
      '/convert': 'http://127.0.0.1:2426',
      '/stream': 'http://127.0.0.1:2426',
    },
  },
});

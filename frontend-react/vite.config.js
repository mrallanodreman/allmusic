import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: './',
  // Los PNG viven una sola vez en public/ (raíz del repo) y se copian al build.
  publicDir: '../public',
  build: { outDir: 'dist', emptyOutDir: true },
  server: {
    proxy: {
      '/radio': 'http://127.0.0.1:2426',
      '/status': 'http://127.0.0.1:2426',
    },
  },
});

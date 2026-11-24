import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// Isolated config for the Complaints regression test: the real data hook is
// replaced with a synchronous mock so the page renders with rows.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [{
      find: '../hooks/useFetch',
      replacement: fileURLToPath(new URL('./mock-useFetch.js', import.meta.url)),
    }],
  },
  build: {
    ssr: true,
    outDir: '.ssr-check',
    emptyOutDir: true,
    rollupOptions: {
      input: fileURLToPath(new URL('./ssr-complaints.jsx', import.meta.url)),
      output: { entryFileNames: 'ssr-complaints.js' },
    },
  },
});

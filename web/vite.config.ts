/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173, strictPort: true },
  preview: { port: 5173 },
  build: {
    // Split heavy vendors into their own long-cacheable chunks (T-37). MapLibre alone
    // is ~800 kB minified, so the per-chunk warning limit is raised accordingly.
    chunkSizeWarningLimit: 1100,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('maplibre-gl')) return 'maplibre';
          if (id.includes('terra-draw')) return 'terra-draw';
          if (id.includes('echarts') || id.includes('zrender')) return 'echarts';
          if (id.includes('/d3-') || id.includes('@turf') || id.includes('internmap')) return 'geo';
          if (id.includes('react') || id.includes('scheduler') || id.includes('@tanstack'))
            return 'react';
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
});

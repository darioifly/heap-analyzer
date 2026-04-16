import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    include: [
      'frontend/src/**/*.{test,spec}.{ts,tsx}',
      'electron/src/**/*.{test,spec}.{ts,tsx}',
    ],
    coverage: {
      reporter: ['text', 'lcov'],
      include: ['frontend/src/**', 'electron/src/**'],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'frontend/src'),
    },
  },
});

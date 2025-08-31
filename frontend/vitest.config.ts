import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],        // 👈 React transform for .js/.jsx/.tsx
  test: {
    include: ['tests/unit/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['tests/e2e/**'],
    environment: 'jsdom',
    globals: true,
    setupFiles: [
      'tests/unit/setup-dom.ts',
      'tests/unit/mocks/server.ts',
    ],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
});

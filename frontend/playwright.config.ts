import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'tests/e2e',                 // only e2e here
  testMatch: /.*\.spec\.ts$/,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    headless: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: true,
    timeout: 120_000,
  },
  workers: 1, // Next dev server behaves nicer with single worker
});

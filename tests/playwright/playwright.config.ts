import { defineConfig } from '@playwright/test';
import path from 'path';

export default defineConfig({
  testDir: path.join(__dirname),
  timeout: 30_000,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    screenshot: 'only-on-failure',
  },
  outputDir: 'test-results',
  projects: [
    {
      name: 'electron-smoke',
      testMatch: 'smoke.spec.ts',
    },
  ],
});

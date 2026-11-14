import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://localhost:5173' },
  webServer: { command: 'pnpm dev', url: 'http://localhost:5173', reuseExistingServer: true },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 1000 },
        // Software WebGL so the MapLibre globe renders in headless CI.
        launchOptions: { args: ['--use-gl=swiftshader', '--enable-webgl'] },
      },
    },
  ],
  retries: process.env.CI ? 1 : 0,
});

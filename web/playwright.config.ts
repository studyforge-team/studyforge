import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: 'tests',
  timeout: 240_000,
  use: { baseURL: 'http://localhost:4192', browserName: 'chromium' },
  webServer: {
    command: 'npm run build && npx vite preview --port 4192 --strictPort',
    url: 'http://localhost:4192',
    reuseExistingServer: false,
    timeout: 600_000,
  },
})

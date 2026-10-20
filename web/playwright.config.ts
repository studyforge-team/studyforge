import { defineConfig } from '@playwright/test'
import os from 'os'
import path from 'path'

export default defineConfig({
  testDir: 'tests',
  timeout: 240_000,
  outputDir: path.join(os.tmpdir(), 'studyforge-playwright-results'),
  use: { baseURL: 'http://localhost:4192', browserName: 'chromium' },
  webServer: {
    command: 'npm run build && npx vite preview --port 4192 --strictPort',
    url: 'http://localhost:4192',
    reuseExistingServer: false,
    timeout: 600_000,
  },
})

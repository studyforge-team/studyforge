import fs from 'node:fs'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

// Applies vercel.json headers in `vite preview` so the CSP is exercised locally, not only on Vercel.
// Later rules overwrite earlier ones for the same header key (how Vercel resolves duplicates).
function vercelHeaders(): Plugin {
  const rules = (
    JSON.parse(fs.readFileSync('vercel.json', 'utf8')) as {
      headers: { source: string; headers: { key: string; value: string }[] }[]
    }
  ).headers.map((r) => ({ re: new RegExp(`^${r.source}$`), headers: r.headers }))
  return {
    name: 'vercel-headers',
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        const p = (req.url ?? '').split('?')[0]
        for (const r of rules) if (r.re.test(p)) for (const h of r.headers) res.setHeader(h.key, h.value)
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), vercelHeaders()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  worker: { format: 'es' },
  optimizeDeps: { exclude: ['pyodide'] },
})

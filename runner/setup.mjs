// Copies the Pyodide files built by `cd web && npm ci && node scripts/copy-pyodide.mjs`
// into runner/pyodide/ (gitignored) so the docker mount of runner/ carries them.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const src = path.join(here, '..', 'web', 'public', 'pyodide', '314.0.7')
if (!fs.existsSync(src)) throw new Error(`${src} missing: run node scripts/copy-pyodide.mjs in web/ first`)
fs.cpSync(src, path.join(here, 'pyodide', '314.0.7'), { recursive: true })
console.log('runner/pyodide/314.0.7 ready')

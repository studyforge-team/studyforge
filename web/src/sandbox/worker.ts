// Pyodide sandbox worker. Everything it posts is untrusted by the page (Python can call
// js.postMessage), so client.ts validates every message.
import type { PyodideInterface, loadPyodide } from 'pyodide'

const BASE = '/pyodide/314.0.7/'
const NET = ['fetch', 'XMLHttpRequest', 'WebSocket', 'WebSocketStream', 'EventSource', 'Worker',
  'SharedWorker', 'caches', 'WebTransport', 'BroadcastChannel', 'indexedDB']
const ALLOWED = ['numpy', 'scipy', 'sympy', 'matplotlib']
const CAP = 65536

type In = { type: 'init'; packages: string[] } | { type: 'run'; id: number; code: string; mode: 'solve' | 'chemlab' }

let py: PyodideInterface
let locked = false // true once user code has run: network is gone, no more loading
const post = (m: unknown) => self.postMessage(m)
const quiet = { messageCallback: () => {} }

// numpy scalars/arrays -> plain lists/floats; anything else -> str. allow_nan=False raises on NaN/inf.
const DUMP = `import json as _j
_out = _j.dumps(result, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o), allow_nan=False)`
const FIGS = `import io, base64, json
import matplotlib.pyplot as plt
figs, notes = [], []
for i, n in enumerate(plt.get_fignums()):
    if i >= 4:
        notes.append("[figure limit: only the first 4 figures are returned]")
        break
    b = io.BytesIO()
    plt.figure(n).savefig(b, format="png")
    if b.tell() > 500000:
        notes.append(f"[figure {n} dropped: PNG over 500 KB]")
    else:
        figs.append(base64.b64encode(b.getvalue()).decode())
plt.close("all")
json.dumps({"figs": figs, "notes": notes})`

async function load(pkgs: string[]) {
  await py.loadPackage(pkgs, quiet)
  // Pre-import so import time is not charged to the 10 s user-code timer.
  if (pkgs.includes('matplotlib')) await py.runPythonAsync('import matplotlib\nmatplotlib.use("Agg")\nimport matplotlib.pyplot')
  if (pkgs.includes('sympy')) await py.runPythonAsync('import sympy')
}

// Removes network APIs from self and from every object on its prototype chain.
function lockdown() {
  for (let o: object | null = self; o && o !== Object.prototype; o = Object.getPrototypeOf(o)) {
    for (const k of NET) {
      if (!Object.prototype.hasOwnProperty.call(o, k)) continue
      delete (o as Record<string, unknown>)[k]
      if (Object.prototype.hasOwnProperty.call(o, k)) Object.defineProperty(o, k, { value: undefined, writable: false, configurable: false })
    }
  }
  py.runPython("import sys\nsys.modules.pop('pyodide_js', None)\nsys.modules.pop('micropip', None)")
  py.unregisterJsModule('pyodide_js')
  locked = true
}

async function init(packages: string[]) {
  const t = performance.now()
  const mod = (await import(/* @vite-ignore */ `${BASE}pyodide.mjs`)) as { loadPyodide: typeof loadPyodide }
  py = await mod.loadPyodide({ indexURL: BASE })
  await py.loadPackage(['numpy', 'scipy', ...packages], quiet)
  await py.runPythonAsync('import numpy, scipy.optimize, scipy.integrate')
  const extra = packages.filter((p) => p === 'matplotlib' || p === 'sympy')
  await load(extra)
  post({ type: 'ready', ms: Math.round(performance.now() - t) })
}

async function run(id: number, code: string, mode: 'solve' | 'chemlab') {
  const t = performance.now()
  // ponytail: a mere mention (e.g. a comment) over-loads the package: slower, never wrong
  const need = ALLOWED.filter((p) => new RegExp(String.raw`\b${p}\b`).test(code) && !py.loadedPackages[p])
  if (need.length && locked) return post({ type: 'error', id, error: `needs ${need.join(', ')}`, needsRespawn: need })
  if (need.length) await load(need)
  if (!locked) lockdown()
  let out = ''
  const sink = { batched: (s: string) => { if (out.length <= CAP) out += s + '\n' } }
  py.setStdout(sink)
  py.setStderr(sink)
  const ns = py.globals.get('dict')()
  post({ type: 'started', id })
  try {
    await py.runPythonAsync(code, { globals: ns })
    if (!ns.has('result')) throw new Error('code must set result = {...}')
    py.runPython(DUMP, { globals: ns })
    const json = ns.get('_out') as string
    // ponytail: the 16 KB cap counts UTF-16 units of the JSON string, close enough to bytes for numeric results.
    if (mode === 'solve' && json.length > 16384) throw new Error('result too large')
    let figures: string[] = []
    if (py.loadedPackages.matplotlib) {
      const f = JSON.parse(py.runPython(FIGS) as string) as { figs: string[]; notes: string[] }
      figures = f.figs
      for (const n of f.notes) out += n + '\n'
    }
    if (out.length > CAP) out = out.slice(0, CAP) + '\n[output truncated]'
    post({ type: 'result', id, result: JSON.parse(json), stdout: out, figures, ms: Math.round(performance.now() - t) })
  } catch (e) {
    if (py.loadedPackages.matplotlib) py.runPython('import matplotlib.pyplot as plt\nplt.close("all")')
    post({ type: 'error', id, error: String((e as Error).message || e).slice(-600) })
  } finally {
    ns.destroy()
  }
}

self.onmessage = async ({ data }: MessageEvent<In>) => {
  try {
    if (data.type === 'init') await init(data.packages)
    else await run(data.id, data.code, data.mode)
  } catch (e) {
    post({ type: 'fatal', error: String((e as Error).message || e).slice(-800) })
  }
}

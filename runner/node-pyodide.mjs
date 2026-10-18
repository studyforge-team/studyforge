// CI/eval runner (ticket S1b): one JSON line {"code","timeout_s"} on stdin -> exactly one
// ResultBody JSON line on stdout. Mirrors web/src/sandbox/worker.ts. Meant to run ONLY inside
// `docker --network none` with an empty env and `node --permission --allow-fs-read=/runner`;
// the lockdown below is a third, in-process layer. Diagnostics go to stderr.
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

// Saved before lockdown: user code can reach globalThis, not these module bindings.
const proc = process
const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), 'pyodide', '314.0.7')
const NET = ['fetch', 'XMLHttpRequest', 'WebSocket', 'WebSocketStream', 'EventSource', 'Worker',
  'SharedWorker', 'caches', 'WebTransport', 'BroadcastChannel', 'indexedDB', 'MessageChannel',
  'MessagePort', 'Navigator', 'navigator', 'require', 'Bun', 'Deno']
const ALLOWED = ['numpy', 'scipy', 'sympy', 'matplotlib']
const CAP = 65536

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

// Emscripten's NODEFS init calls process.binding('constants'), which --permission denies.
// Serve just that one binding from the public fs.constants; NODEFS is never mounted.
const realBinding = proc.binding
proc.binding = (n) => (n === 'constants' ? { fs: fs.constants } : realBinding.call(proc, n))

const emit = (body) => proc.stdout.write(JSON.stringify(body) + '\n', () => proc.exit(0))

async function readLine() {
  let s = ''
  for await (const c of proc.stdin) s += c
  return s.split('\n')[0]
}

// Strip network / process access from globalThis (and its prototype chain) before user code.
function lockdown(py) {
  for (let o = globalThis; o && o !== Object.prototype; o = Object.getPrototypeOf(o)) {
    for (const k of NET) {
      if (!Object.prototype.hasOwnProperty.call(o, k)) continue
      delete o[k]
    }
  }
  // Frozen empty stub: Function('return process')() and js.eval('process') see nothing.
  Object.defineProperty(globalThis, 'process', { value: Object.freeze({}), configurable: false, writable: false })
  py.runPython("import sys\nsys.modules.pop('pyodide_js', None)\nsys.modules.pop('micropip', None)")
  py.unregisterJsModule('pyodide_js')
}

async function main() {
  const t = performance.now()
  const req = JSON.parse(await readLine())
  const code = String(req.code)
  // ponytail: this timer only fires if user code yields; the docker kill in NodeRunner is the
  // hard stop for a CPU-bound loop (no worker thread, so no extra permission grants).
  const timer = setTimeout(() => emit({ error: 'timeout', ms: Math.round(performance.now() - t) }), Math.max(0.1, +req.timeout_s || 10) * 1000)
  const { loadPyodide } = await import(pathToFileURL(path.join(dir, 'pyodide.mjs')).href)
  const quiet = { messageCallback: () => {}, errorCallback: () => {} }
  const py = await loadPyodide({ indexURL: dir + path.sep, stdout: () => {}, stderr: (s) => proc.stderr.write(s + '\n') })
  const pkgs = ['numpy', 'scipy', ...ALLOWED.slice(2).filter((p) => new RegExp(String.raw`\b${p}\b`).test(code))]
  await py.loadPackage(pkgs, quiet)
  await py.runPythonAsync('import numpy, scipy.optimize, scipy.integrate')
  if (pkgs.includes('matplotlib')) await py.runPythonAsync('import matplotlib\nmatplotlib.use("Agg")\nimport matplotlib.pyplot')
  if (pkgs.includes('sympy')) await py.runPythonAsync('import sympy')
  lockdown(py)
  let out = ''
  const sink = { batched: (s) => { if (out.length <= CAP) out += s + '\n' } }
  py.setStdout(sink)
  py.setStderr(sink)
  const ns = py.globals.get('dict')()
  const t0 = performance.now()
  try {
    await py.runPythonAsync(code, { globals: ns })
    if (!ns.has('result')) throw new Error('code must set result = {...}')
    py.runPython(DUMP, { globals: ns })
    const json = ns.get('_out')
    if (json.length > 16384) throw new Error('result too large')
    let figures = []
    if (py.loadedPackages.matplotlib) {
      const f = JSON.parse(py.runPython(FIGS))
      figures = f.figs
      for (const n of f.notes) out += n + '\n'
    }
    if (out.length > CAP) out = out.slice(0, CAP) + '\n[output truncated]'
    clearTimeout(timer)
    emit({ stdout: out, result: JSON.parse(json), figures, error: null, ms: Math.round(performance.now() - t0) })
  } catch (e) {
    clearTimeout(timer)
    emit({ error: String(e?.message || e).slice(-600), ms: Math.round(performance.now() - t0) })
  }
}

main().catch((e) => emit({ error: String(e?.message || e).slice(-600), ms: 0 }))

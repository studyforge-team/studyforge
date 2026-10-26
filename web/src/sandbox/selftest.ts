// Sandbox self-test: functional, kill, 20 escape probes, memory. Uses only the public client API.
import { run, type SandboxResult } from './client'

type Row = { name: string; pass: boolean; detail: string }
const rows: Row[] = []
let onRow: ((done: number) => void) | undefined // ponytail: progress callback for the slow first run on phones
const add = (name: string, pass: boolean, detail: string) => { rows.push({ name, pass, detail: detail.slice(-200) }); onRow?.(rows.length) }
export let readyS = 0 // seconds until the first run finished: download + Python start + numpy/scipy (G13 number)
const err = (r: SandboxResult) => (r.ok ? '' : r.error)
const last = (s: string) => s.trim().split('\n').pop() ?? ''
const trivial = async () => {
  const r = await run('result = {"v": 41 + 1}')
  return r.ok && (r.result as { v: number }).v === 42
}

// [name, python, substring the error must contain (when "no exception" alone is not proof)]
const PROBES: [string, string, string?][] = [
  ['from js import fetch', 'from js import fetch\nfetch'],
  ['js.fetch("/")', 'import js\nawait js.fetch("/")'],
  ['proto chain fetch', 'import js\no = js.Object.getPrototypeOf(js.self)\nfound = []\nwhile o:\n    if js.Object.prototype.hasOwnProperty.call(o, "fetch"): found.append(1)\n    o = js.Object.getPrototypeOf(o)\nassert not found, "fetch still on prototype"\nraise Exception("no fetch anywhere")', 'no fetch anywhere'],
  ['globalThis.fetch', 'import js\nf = getattr(js.globalThis, "fetch", None)\nassert f is None or f is js.undefined, "present"\nraise Exception("absent")', 'absent'],
  ['js.eval', 'import js\njs.eval("1+1")'],
  ['js.Function', 'import js\njs.Function.new("return 1")()'],
  ['run_js', 'from pyodide.code import run_js\nrun_js("1+1")'],
  ['XMLHttpRequest', 'import js\njs.XMLHttpRequest.new()'],
  ['WebSocket', 'import js\njs.WebSocket.new("wss://example.com")'],
  ['WebSocketStream', 'import js\njs.WebSocketStream.new("wss://example.com")'],
  ['EventSource', 'import js\njs.EventSource.new("/x")'],
  ['nested Worker', 'import js\njs.Worker.new("/x.js")'],
  ['caches.open', 'import js\nawait js.caches.open("x")'],
  ['indexedDB.open', 'import js\njs.indexedDB.open("x")'],
  ['BroadcastChannel', 'import js\njs.BroadcastChannel.new("x")'],
  ['import pyodide_js', 'import pyodide_js\npyodide_js.loadPackage', 'pyodide_js'],
  ['import micropip', 'import micropip', 'micropip'],
  ['pyfetch', 'from pyodide.http import pyfetch\nawait pyfetch("/")'],
  ['dynamic import()', 'import js\njs.Function.new("return import(\'/x.js\')")()'],
  ['forged postMessage', 'import js\nfrom pyodide.ffi import to_js\njs.postMessage(to_js({"type":"result","id":999,"stdout":"<img src=x onerror=alert(1)>","figures":["nope"],"ms":1,"result":{}}, dict_converter=js.Object.fromEntries))\nraise Exception("sent forged message")', 'sent forged message'],
]

export async function selftest(progress?: (done: number) => void): Promise<Row[]> {
  rows.length = 0
  onRow = progress
  const start = performance.now()
  let csp = 0
  const onCsp = () => csp++
  document.addEventListener('securitypolicyviolation', onCsp)

  // functional
  let r = await run(`import numpy as np
from scipy.optimize import brentq
ca0, tau, k = 2.0, 5.0, 0.3
ca = brentq(lambda c: (ca0 - c) / tau - k * c, 0, ca0)
result = {"ca": np.float64(ca), "arr": np.arange(3)}`)
  readyS = Math.round((performance.now() - start) / 100) / 10
  const ca = r.ok ? (r.result as { ca: number }).ca : NaN
  add('numpy+scipy brentq steady state', r.ok && Math.abs(ca - 0.8) < 1e-6, r.ok ? `ca=${ca}` : err(r))

  r = await run('import matplotlib.pyplot as plt\nplt.plot([1, 2, 3])\nresult = {"n": 1}')
  add('matplotlib figure', r.ok && r.figures.length === 1 && r.figures[0].startsWith('iVBORw0KGgo'), r.ok ? `${r.figures.length} figure(s)` : err(r))

  r = await run('import numpy as np, matplotlib.pyplot as plt\nplt.plot(np.arange(3))\nresult = {}')
  add('one-line multi-import plot', r.ok && r.figures.length === 1, r.ok ? `${r.figures.length} figure(s)` : err(r))

  r = await run('import sympy as sp\nx = sp.symbols("x")\nresult = {"d": str(sp.diff(sp.sin(x) * x, x))}')
  const d = r.ok ? (r.result as { d: string }).d : ''
  add('sympy diff', d === 'x*cos(x) + sin(x)', r.ok ? d : err(r))

  r = await run('print("x" * 200000)\nresult = {}')
  add('200 KB print truncated', r.ok && r.stdout.endsWith('[output truncated]') && r.stdout.length <= 65536 + 20, r.ok ? `stdout length ${r.stdout.length}` : err(r))

  r = await run('x = 1')
  add('missing result', !r.ok && r.error.includes('result'), err(r) || 'unexpected ok')

  r = await run('print("Tc", 369.8)\n369.8 / 2')
  add('missing result shows output', !r.ok && r.error.includes('Tc 369.8') && r.error.includes('Last expression: 184.9') && r.error.endsWith('(this run set no result)'), err(r) || 'unexpected ok')

  r = await run('from chemlab._correlations import lee_kesler, cubic_psat, bubble_t\nZ, h, s, lp = lee_kesler(1.2, 0.66, 0.0)\np = cubic_psat(300.0, 369.8, 42.48e5, 0.152)\nb = bubble_t([0.5, 0.5], 101.325, [lambda t: 10**(6.90565 - 1211.033/(t + 220.79))*0.133322, lambda t: 10**(6.95464 - 1344.8/(t + 219.482))*0.133322], T0=90)\nresult = {"Z": Z, "psat_bar": p.Psat / 1e5, "T": b.T}')
  const tools = r.ok ? (r.result as { Z: number; psat_bar: number; T: number }) : undefined
  add('chemlab tools: Lee-Kesler, PR Psat, bubble T', !!tools && Math.abs(tools.Z - 0.865) < 0.003 && Math.abs(tools.psat_bar - 9.99) < 0.1 && tools.T > 80 && tools.T < 100, r.ok ? JSON.stringify(r.result) : err(r))

  r = await run('import numpy as np\na = np.zeros(2, dtype=float)\nx = np.linalg.solve(np.eye(2, dtype=float), np.ones(2))\nresult = {"dtype": str(a.dtype), "x": x.tolist()}')
  add('dtype=float stays float64', r.ok && (r.result as { dtype: string }).dtype === 'float64', r.ok ? JSON.stringify(r.result) : err(r))

  r = await run('from scipy.optimize import fsolve\nv = float(fsolve(lambda x: x**2 - 4, 1.0))\nresult = {"v": v, "isfloat": isinstance(v, float)}')
  add('float() of a one-element array', r.ok && Math.abs((r.result as { v: number }).v - 2) < 1e-9 && (r.result as { isfloat: boolean }).isfloat, r.ok ? JSON.stringify(r.result) : err(r))

  r = await run('result = {"a": list(range(10000))}')
  add('solve result > 16 KB', !r.ok && r.error.includes('result too large'), err(r) || 'unexpected ok')

  r = await run('result = {"a": list(range(10000))}', { mode: 'chemlab' })
  add('chemlab result uncapped', r.ok, err(r) || 'ok')

  // ponytail: no chemlab files bundled (main today) -> the package itself is missing -> row skipped; a broken bundle still fails
  r = await run('from chemlab.cstr import run\nr = run({}, series=False)\nresult = {"ok": r["ok"], "n": r["n_steady_states"], "stable": [s["stable"] for s in r["steady_states"]]}', { mode: 'chemlab' })
  if (r.ok || !r.error.includes("No module named 'chemlab'")) {
    const c = r.ok ? (r.result as { n: number; stable: boolean[] }) : undefined
    add('chemlab: CSTR default has 3 steady states', !!c && c.n === 3 && JSON.stringify(c.stable) === '[true,false,true]', r.ok ? JSON.stringify(c) : err(r))
  }

  document.removeEventListener('securitypolicyviolation', onCsp)
  add('no CSP violations during normal runs', csp === 0, `${csp} violation(s)`)

  // kill
  const t0 = performance.now()
  r = await run('while True:\n    pass')
  add('infinite loop is killed', !r.ok && r.error === 'timeout', `${err(r) || 'unexpected ok'} after ${Math.round(performance.now() - t0)} ms`)
  add('run succeeds after kill', await trivial(), 'respawned')

  // forged results for guessable ids, then a hang: the hard deadline must still fire
  const t1 = performance.now()
  r = await run('import js\nfrom pyodide.ffi import to_js\nfor i in range(1, 51):\n    js.postMessage(to_js({"type":"result","id":i,"stdout":"","figures":[],"ms":0,"result":{}}, dict_converter=js.Object.fromEntries))\nwhile True:\n    pass')
  const ms1 = Math.round(performance.now() - t1)
  add('forged result + hang is killed', !r.ok && r.error === 'timeout' && ms1 < 11500 && (await trivial()), `${err(r) || 'unexpected ok'} after ${ms1} ms`)

  // escapes: each must fail inside Python (or, for the forged message, the client must stay healthy)
  for (const [name, code, must] of PROBES) {
    r = await run(`${code}\nresult = {"escaped": True}`)
    const e = err(r)
    add(`escape: ${name}`, !r.ok && e !== 'timeout' && (!must || e.includes(must)), r.ok ? 'ESCAPED' : last(e))
  }
  add('escape: client healthy after forged postMessage', await trivial(), 'next run returned 42')

  // memory
  r = await run('import numpy as np\na = np.ones(2**28)\nresult = {"n": int(a.size)}')
  add('2 GB allocation fails safely', !r.ok, r.ok ? 'allocation succeeded' : last(r.error))
  add('run succeeds after memory failure', await trivial(), 'ok')

  return [...rows]
}

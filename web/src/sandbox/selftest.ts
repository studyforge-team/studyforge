// Sandbox self-test: functional, kill, 20 escape probes, memory. Uses only the public client API.
import { run, type SandboxResult } from './client'

type Row = { name: string; pass: boolean; detail: string }
const rows: Row[] = []
const add = (name: string, pass: boolean, detail: string) => rows.push({ name, pass, detail: detail.slice(-200) })
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

export async function selftest(): Promise<Row[]> {
  rows.length = 0
  let csp = 0
  const onCsp = () => csp++
  document.addEventListener('securitypolicyviolation', onCsp)

  // functional
  let r = await run(`import numpy as np
from scipy.optimize import brentq
ca0, tau, k = 2.0, 5.0, 0.3
ca = brentq(lambda c: (ca0 - c) / tau - k * c, 0, ca0)
result = {"ca": np.float64(ca), "arr": np.arange(3)}`)
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

  r = await run('result = {"a": list(range(10000))}')
  add('solve result > 16 KB', !r.ok && r.error.includes('result too large'), err(r) || 'unexpected ok')

  r = await run('result = {"a": list(range(10000))}', { mode: 'chemlab' })
  add('chemlab result uncapped', r.ok, err(r) || 'ok')

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

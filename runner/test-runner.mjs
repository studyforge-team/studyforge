// Local protocol + attack tests, no docker: node --test runner/test-runner.mjs
// Needs runner/pyodide (node runner/setup.mjs). Spawns the runner under `node --permission`
// exactly like the container does; the docker layer itself is tested by api/tests/runner.
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const dir = path.dirname(fileURLToPath(import.meta.url))
const have = fs.existsSync(path.join(dir, 'pyodide'))
const attacks = JSON.parse(fs.readFileSync(path.join(dir, 'attacks.json'), 'utf8'))
const CANARY = 'canary-' + process.pid
const flags = process.env.RUNNER_NO_PERMISSION ? [] : ['--permission', `--allow-fs-read=${dir}`]

function run(code, timeout_s = 60) {
  const p = spawnSync('node', [...flags, path.join(dir, 'node-pyodide.mjs')], {
    input: JSON.stringify({ code, timeout_s }) + '\n', encoding: 'utf8', env: { ...process.env, SF_CANARY_SECRET: CANARY }, timeout: 120000,
  })
  const lines = p.stdout.split('\n').filter(Boolean)
  assert.ok(lines.length >= 1, `no reply: ${p.stderr}`)
  assert.equal(lines.length, 1, 'exactly one stdout line')
  assert.ok(!p.stdout.includes(CANARY) && !p.stderr.includes(CANARY), 'canary leaked')
  return JSON.parse(lines[0])
}

for (const [name, code] of Object.entries(attacks)) {
  test(`attack ${name} fails`, { skip: !have }, () => {
    const r = run(code)
    assert.ok(r.error || r.result.ok === false, JSON.stringify(r))
  })
}

test('process global is an empty stub', { skip: !have }, () => {
  const r = run("import js\nresult = {'keys': str(js.Object.keys(js.process).to_py()), 'ty': str(js.eval('typeof process.env'))}")
  assert.deepEqual(r.result, { keys: '[]', ty: 'undefined' })
})

test('numpy/scipy fsolve, print captured', { skip: !have }, () => {
  const r = run('import numpy as np\nfrom scipy.optimize import fsolve\nprint("hi")\nresult = {"x": float(fsolve(lambda x: x**2 - 4, 1.0)[0]), "arr": np.arange(3)}')
  assert.equal(r.error, null)
  assert.equal(r.stdout, 'hi\n')
  assert.ok(Math.abs(r.result.x - 2) < 1e-6)
  assert.deepEqual(r.result.arr, [0, 1, 2])
})

test('matplotlib figure returns base64 PNG', { skip: !have }, () => {
  const r = run('import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nresult = {"n": 1}')
  assert.equal(r.figures.length, 1)
  assert.equal(Buffer.from(r.figures[0], 'base64').subarray(1, 4).toString(), 'PNG')
})

test('missing result and NaN are errors', { skip: !have }, () => {
  assert.match(run('x = 1').error, /result/)
  assert.ok(run('result = {"a": float("nan")}').error)
})

test('internal timeout fires when user code yields', { skip: !have }, () => {
  const r = run('import asyncio\nawait asyncio.sleep(30)\nresult = {}', 2)
  assert.equal(r.error, 'timeout')
})

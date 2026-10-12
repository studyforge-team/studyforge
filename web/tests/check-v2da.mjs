// Run from the repo root:  node --experimental-strip-types web/tests/check-v2da.mjs   (Node >= 22.6; Node 24 needs no flag)
import assert from 'node:assert/strict'
import { cstrViews } from '../src/chemlab/drawings/cstr.ts'

const sheet = (V, UA = 0) => {
  const D = ((4 * V) / Math.PI) ** (1 / 3) // same as cstr.py: H = D
  const inputs = { V: { value: V, unit: 'm^3' }, UA: { value: UA, unit: 'W/K' } }
  return cstrViews({ diameter_m: D, height_m: D }, inputs)
}
const dim = (svg, key) => Number(new RegExp(`>${key} = ([0-9]+) mm`).exec(svg)?.[1]) // dimension-line text only

// tiny XML check: tags balance and every attribute is quoted
const xmlOk = (svg) => {
  const st = []
  for (const [, close, name, , self] of svg.matchAll(/<(\/?)([\w:-]+)((?:[^>"]|"[^"]*")*?)(\/?)>/g)) {
    if (self) continue
    if (close) assert.equal(st.pop(), name, `unbalanced </${name}>`)
    else st.push(name)
  }
  assert.equal(st.length, 0, 'unclosed tags')
}

const a = sheet(1), b = sheet(4), j = sheet(1, 5000)
xmlOk(a); xmlOk(b); xmlOk(j)

assert.ok(dim(b, 'D') > dim(a, 'D') && dim(b, 'H') > dim(a, 'H'), 'larger V must draw larger D and H')
assert.equal(dim(a, 'D'), Math.round(((4 / Math.PI) ** (1 / 3)) * 1000)) // V = 1 -> D = 1084 mm
assert.equal(dim(a, 'H'), dim(a, 'D'))
assert.match(a, /d = D\/3 = 361 mm/) // impeller diameter
assert.match(a, /Liquid level = 867 mm/)
for (const t of ['FRONT ELEVATION', 'PLAN', 'LEFT-HAND SIDE VIEW', 'FIRST ANGLE PROJECTION', 'general arrangement', 'V = 1 m^3'])
  assert.ok(a.includes(t), `missing ${t}`)
assert.equal(a.match(/class="baf"/g).length, 2 + 2 + 4, 'baffles: 2 strips front, 2 side, 4 in plan')
assert.ok(!a.includes('Jacket') && j.includes('Jacket'), 'jacket only when UA > 0')
assert.match(a, /role="img"/); assert.match(a, /<title id=/); assert.match(a, /<desc id=/)

const ids = (s) => [...s.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1])
const all = [...ids(a), ...ids(b)]
assert.equal(new Set(all).size, all.length, 'ids must be unique across sheets on one page')
console.log('V2Da checks passed')

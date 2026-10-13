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
// scale: V = 1 m^3 is reduced (1:n); V = 1 L (D = 108 mm) is enlarged and must read n:1, never 1:0
assert.match(a, /Approx\. 1:[1-9][0-9]*;/)
assert.match(sheet(0.001), /Approx\. [2-9]:1;/)

assert.ok(dim(b, 'D') > dim(a, 'D') && dim(b, 'H') > dim(a, 'H'), 'larger V must draw larger D and H')
assert.equal(dim(a, 'D'), Math.round(((4 / Math.PI) ** (1 / 3)) * 1000)) // V = 1 -> D = 1084 mm
assert.equal(dim(a, 'H'), dim(a, 'D'))
assert.match(a, /d = D\/3 = 361 mm/) // impeller diameter
assert.match(a, /Liquid level = 867 mm/)
for (const t of ['FRONT ELEVATION', 'PLAN', 'LEFT-HAND SIDE VIEW — HALF SECTION A–A', 'FIRST ANGLE PROJECTION', 'general arrangement', 'V = 1 m^3', 'hatched = cut', 'Shell wall (cut)', 'wall thickness schematic'])
  assert.ok(a.includes(t), `missing ${t}`)
assert.equal(a.match(/class="baf"/g).length, 2 + 1 + 4, 'baffles: 2 strips front, 1 in the cut half of the side view, 4 in plan')
// section: shell, lid and bottom cut (3 bands); a jacket adds its wall, top and bottom closures (3 more,
// hatched the other way so the two cut parts read as separate)
assert.equal(a.match(/class="cut"/g).length, 3, 'cut shell walls')
assert.equal((a.match(/class="cut2"/g) ?? []).length, 0, 'no jacket, no jacket cut')
assert.equal(j.match(/class="cut2"/g).length, 3, 'jacket wall + top + bottom closure')
assert.ok(j.includes('Jacket (cut)'), 'jacket labelled as cut in the section')
// cutting plane A-A on the plan: two 'A' labels and two chain lines (side-view axis + plan cutting plane)
assert.equal(a.match(/>A<\/text>/g).length, 2, 'cutting plane A-A labelled at both ends')
assert.equal(a.match(/class="cl"/g).length, 2, 'chain lines: side-view axis and plan cutting plane')
// halves split exactly at the side-view axis: left clip width = right clip x = axis x
const clipL = /<clipPath id="[^"]+L"><rect x="0" y="0" width="([\d.]+)"/.exec(a), clipR = /<clipPath id="[^"]+R"><rect x="([\d.]+)"/.exec(a)
const axis = [...a.matchAll(/<line class="cl" x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)"/g)].map((m) => [+m[1], +m[2]])
assert.ok(clipL && clipR && clipL[1] === clipR[1], 'clip halves meet')
assert.ok(axis.some(([x1, x2]) => x1 === x2 && String(x1) === clipR[1]), 'halves meet on the drawn axis')
// the shaft below the lid is only drawn inside the cut half (one 'sh' rect per view inside clip R, none in L)
const inL = /clip-path="url\(#[^)]+L\)">([\s\S]*?)<\/g>/.exec(a)[1]
assert.ok(!inL.includes('class="sh"') && !inL.includes('class="cut'), 'outside half shows no shaft and no cut')
// viewing-direction arrows on the plan point +x (the side view looks from -x)
const planArrows = [...a.matchAll(/<line class="l" x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" marker-end/g)]
  .filter((m) => m[2] === m[4] && +m[3] - +m[1] === 16)
assert.equal(planArrows.length, 2, 'two A-A arrows')
// every url(#id) reference resolves to an id defined in the same sheet
for (const svg of [a, j]) for (const [, ref] of svg.matchAll(/url\(#([^)]+)\)/g)) assert.ok(svg.includes(`id="${ref}"`), `dangling url(#${ref})`)
assert.ok(!a.includes('Jacket') && j.includes('Jacket'), 'jacket only when UA > 0')
assert.match(a, /role="img"/); assert.match(a, /<title id=/); assert.match(a, /<desc id=/)

const ids = (s) => [...s.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1])
const all = [...ids(a), ...ids(b)]
assert.equal(new Set(all).size, all.length, 'ids must be unique across sheets on one page')
console.log('V2Da checks passed')

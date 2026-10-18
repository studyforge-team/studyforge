import { expect, test } from '@playwright/test'
import { pfrViews } from '../src/chemlab/drawings/pfr.ts'
import { sig } from '../src/chemlab/drawings/sheet.ts'

const inputs = Object.fromEntries(['V', 'v0', 'D', 'CA0', 'k', 'n', 'T'].map((k, i) => [k, { value: i + 1, unit: '-' }]))
// the pfr template's geometry rule (chemlab/templates/pfr.py): L = 4 V / (pi D^2)
const geo = (V: number, D: number) => ({ type: 'pfr', length_m: (4 * V) / (Math.PI * D ** 2), diameter_m: D, volume_m3: V })

test('pfr drawing: long tube is broken, dimensioned at its true length, and says so', () => {
  const g = geo(1, 0.1)
  const s = pfrViews(g, inputs)
  for (const t of ['FRONT ELEVATION', 'SECTION A–A', 'FIRST ANGLE PROJECTION', 'Feed in', 'Product out', 'Tubular reactor (PFR)',
    `L = ${sig(g.length_m)} m`, 'Ø D = 100 mm', 'V = 1 m³', 'Length broken: not to scale.', 'Wall not to scale.', 'V = 1 -'])
    expect(s).toContain(t)
  expect(sig(g.length_m)).toBe('127.3')
  expect(s).toContain('L = 127.3 m')
})

test('pfr drawing: short tube is drawn unbroken at a stated scale', () => {
  const g = geo(0.005, 0.1) // 0.64 m, L/D ~ 6
  const s = pfrViews(g, inputs)
  expect(s).toContain(`L = ${sig(g.length_m)} m`)
  expect(s).toContain('Ø D = 100 mm')
  expect(s).toContain('V = 0.005 m³')
  expect(s).not.toContain('broken')
  expect(s).toMatch(/Elevation approx\. (1:\d+|[\d.]+:1) at 1000 mm sheet width/)
})

test('pfr drawing: small bore keeps its significant figures', () => {
  const s = pfrViews(geo(1e-4, 0.0024), inputs)
  expect(s).toContain('2.4 mm')
  expect(s).not.toContain('Ø D = 2 mm')
})

test('pfr drawing: bores of 10 mm and more keep 4 significant figures', () => {
  expect(pfrViews(geo(0.01, 0.0254), inputs)).toContain('Ø D = 25.4 mm')
  expect(pfrViews(geo(0.01, 0.0125), inputs)).toContain('12.5 mm')
})

test('pfr drawing: short wide tube gets a minimum drawn length, true dimension text', () => {
  const g = geo(0.2, 10) // L ~ 0.00255 m
  const s = pfrViews(g, inputs)
  expect(s).toContain(`L = ${sig(g.length_m)} m`)
  expect(s).toContain('Length drawn enlarged: not to scale.')
  expect(s).not.toMatch(/Elevation approx\./)
  // the elevation tube is the only o2 rect on the sheet besides the 980 px border
  const tube = [...s.matchAll(/<rect class="o2" x="[\d.]+" y="[\d.]+" width="([\d.]+)"/g)].map((m) => +m[1]).filter((w) => w < 900)
  expect(tube).toHaveLength(1)
  expect(tube[0]).toBeGreaterThanOrEqual(140)
  expect(s).not.toContain('width="0"')
})

test('pfr drawing: finite, escaped, inside the sheet, bad geometry draws nothing', () => {
  const sweep = [geo(1, 0.1), geo(0.005, 0.1), geo(1e-3, 10), geo(10, 1e-3), geo(0.1, 0.05), geo(1, 1)]
  const ids = sweep.flatMap((g) => [...pfrViews(g, inputs).matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]))
  expect(new Set(ids).size).toBe(ids.length)
  for (const g of sweep) {
    const s = pfrViews(g, inputs)
    for (const bad of ['NaN', 'undefined', 'Infinity']) expect(s).not.toContain(bad)
    for (const [, ref] of s.matchAll(/url\(#([^)]+)\)/g)) expect(s).toContain(`id="${ref}"`)
    for (const [, a, v] of s.matchAll(/\b(x|x1|x2|cx|y|y1|y2|cy)="(-?[\d.]+)"/g)) {
      expect(+v, `${a}=${v}`).toBeGreaterThanOrEqual(0)
      expect(+v, `${a}=${v}`).toBeLessThanOrEqual(a.startsWith('x') || a === 'cx' ? 1000 : 700)
    }
    for (const [, x, anchor, attrs, body] of s.matchAll(/<text x="([\d.-]+)" y="[\d.-]+" text-anchor="(\w+)"([^>]*)>([^<]*)</g)) {
      if (attrs.includes('rotate')) continue
      const w = body.length * 6, x0 = +x - (anchor === 'end' ? w : anchor === 'middle' ? w / 2 : 0)
      expect(x0, body).toBeGreaterThanOrEqual(12)
      expect(x0 + w, body).toBeLessThanOrEqual(988)
    }
  }
  const evil = pfrViews(geo(1, 0.1), { 'a<b&c': { value: 1, unit: '<x>' } })
  expect(evil).toContain('a&lt;b&amp;c = 1 &lt;x&gt;')
  expect(evil).not.toContain('<x>')
  for (const g of [{ ...geo(1, 0.1), length_m: NaN }, { ...geo(1, 0.1), diameter_m: 0 }, { ...geo(1, 0.1), volume_m3: -1 }]) expect(pfrViews(g, inputs)).toBe('')
})

test('ChemLab PFR tab shows the drawing from the real template, fits a 375 px phone', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#chemlab/pfr')
  const sheet = page.locator('section', { has: page.getByRole('heading', { name: 'Drawing (2D, first-angle)' }) })
  await expect(sheet).toBeVisible({ timeout: 180_000 })
  await expect(sheet.locator('svg')).toContainText('Tubular reactor (PFR)')
  await expect(sheet.locator('svg')).toContainText('FRONT ELEVATION')
  await expect(sheet.getByRole('button', { name: 'Download SVG' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})

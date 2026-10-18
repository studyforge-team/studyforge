import { expect, test } from '@playwright/test'
import { hxViews, tubeLayout } from '../src/chemlab/drawings/hx.ts'

const inputs = Object.fromEntries(['mh', 'cph', 'Th_in', 'Th_out', 'mc', 'cpc', 'Tc_in', 'U', 'do', 'Lt'].map((k, i) => [k, { value: i + 1, unit: '-' }]))
// the hx template's geometry rule (chemlab/templates/hx.py _geometry): pitch 1.25 do, Db = do (n / 0.249)^(1 / 2.207), shell = Db + 15 mm
const geo = (n: number, d = 0.01905, Lt = 4.88) => {
  const Db = d * (n / 0.249) ** (1 / 2.207)
  return { n_tubes: n, tube_od_m: d, tube_length_m: Lt, pitch_m: 1.25 * d, bundle_diameter_m: Db, shell_diameter_m: Db + 0.015, tube_passes: 2, shell_passes: 1 }
}
const count = (s: string, re: RegExp) => (s.match(re) ?? []).length

test('hx drawing: template defaults (28 tubes) give every view, dimension and tube', () => {
  const s = hxViews(geo(28), inputs)
  for (const t of ['FRONT ELEVATION', 'SECTION C–C (TUBE BUNDLE, 28 TUBES, 2:1)', 'FIRST ANGLE PROJECTION', 'Tube length = 4880 mm',
    '28 tubes, 19 mm OD, 4880 mm long.', 'Triangular pitch 24 mm; 1 shell, 2 tube passes.', 'Bundle 162 mm, shell ID 177 mm.',
    'Shell ID 177 mm', 'Bundle 162 mm (dashed)', 'Tube side in', 'Tube side out', 'Return bonnet', 'Lt = 10 -'])
    expect(s).toContain(t)
  expect(count(s, /class="tube"/g)).toBe(28)
  expect(s).toContain('Shell height drawn ×') // a 177 mm shell on a 4.9 m tube is drawn taller, and the sheet says so
  expect(s).not.toContain('Tube length drawn ×')
  const short = hxViews(geo(50, 0.1, 0.5), inputs) // a 0.5 m tube in a 1.1 m shell is drawn longer, and says so twice
  expect(short).toContain('Tube length drawn ×')
  expect(short).toContain('Tube length = 500 mm (not to scale)')
  for (const sv of [short, s, hxViews(geo(400, 0.1, 3), inputs), hxViews({ ...geo(28), bundle_diameter_m: 0.085, shell_diameter_m: 0.1, tube_length_m: 1.529 }, inputs), hxViews(geo(50, 0.1, 0.62), inputs)]) expect(sv).not.toMatch(/×1(\.0+)?\.(?!\d)/) // a stretch is never printed as ×1.0
})

test('hx tube layout: n tubes, on the pitch, two equal passes, clear of the lane, inside the bundle diameter', () => {
  const bad: string[] = [] // collected, then asserted once: an expect per tube makes this test take minutes
  for (let n = 2; n <= 400; n += 2) {
    const d = 1, p = 1.25, Db = d * (n / 0.249) ** (1 / 2.207)
    const pts = tubeLayout(n, p)
    if (pts.length !== n) bad.push(`n ${n}: ${pts.length} tubes`)
    if (pts.filter(([, y]) => y > 0).length !== n / 2) bad.push(`n ${n}: passes not equal`)
    for (const [x, y] of pts) {
      if (Math.abs(y) < p / 2 - 1e-9) bad.push(`n ${n}: tube in the pass partition lane`)
      if (Math.hypot(x, y) + d / 2 > Db / 2 + 1e-9) bad.push(`n ${n}: tube outside the bundle diameter`)
    }
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++)
      if (Math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) < p - 1e-9) bad.push(`n ${n}: tubes closer than the pitch`)
  }
  expect(bad.slice(0, 5)).toEqual([])
  expect(tubeLayout(1, 1).length).toBe(1)
})

test('hx drawing: large bundles are an outline with the count; bad geometry draws nothing', () => {
  const s = hxViews(geo(9154, 0.01905, 4.88), inputs)
  expect(count(s, /class="tube"/g)).toBe(0)
  expect(s).toContain('9154 tubes (not drawn singly)')
  expect(count(hxViews(geo(400), inputs), /class="tube"/g)).toBe(400)
  for (const g of [{ ...geo(28), n_tubes: 0 }, { ...geo(28), tube_length_m: NaN }, { ...geo(28), pitch_m: 0.01 }, { ...geo(28), shell_diameter_m: -1 }])
    expect(hxViews(g, inputs)).toBe('')
})

test('hx drawing: finite, inside the sheet, text inside the frame, unique ids, valid references', () => {
  // defaults, the template's extremes (do 5-100 mm, Lt 0.5-20 m, U down to 1) and the few-tube cases
  const sweep = [geo(28), geo(8, 0.01905, 20), geo(50, 0.1, 0.5), geo(9154), geo(100, 0.005), geo(2, 0.1, 0.5), geo(4, 0.1, 3), geo(12, 0.1, 0.5), geo(350, 0.01905, 20), geo(2_000_000, 0.1, 0.5)]
    .map((g) => hxViews(g, inputs))
  const ids = sweep.flatMap((s) => [...s.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]))
  expect(new Set(ids).size).toBe(ids.length)
  for (const s of sweep) {
    expect(s).not.toContain('NaN')
    expect(s).toMatch(/Elevation approx\. (1:\d+|[\d.]+:1) at 1000 mm sheet width/)
    for (const [, ref] of s.matchAll(/url\(#([^)]+)\)/g)) expect(s).toContain(`id="${ref}"`)
    for (const [, a, v] of s.matchAll(/\b(x|x1|x2|cx|y|y1|y2|cy)="(-?[\d.]+)"/g)) {
      const lim = a.startsWith('x') || a === 'cx' ? 1000 : 700
      expect(+v, `${a}=${v}`).toBeGreaterThanOrEqual(0)
      expect(+v, `${a}=${v}`).toBeLessThanOrEqual(lim)
    }
    // rough text extent at 11 px Arial (about 6 px a character) must stay inside the 10..990 frame
    const texts = [...s.matchAll(/<text x="([\d.-]+)" y="[\d.-]+" text-anchor="(\w+)">([^<]*)</g)]
    expect(texts.length).toBeGreaterThan(30) // the check below must not pass on an empty match
    for (const [, x, anchor, body] of texts) {
      const w = body.length * 6, x0 = +x - (anchor === 'end' ? w : anchor === 'middle' ? w / 2 : 0)
      expect(x0, body).toBeGreaterThanOrEqual(12)
      expect(x0 + w, body).toBeLessThanOrEqual(988)
    }
  }
})

test('ChemLab heat exchanger tab shows the profile and the drawing from the real template', async ({ page }) => {
  await page.goto('/#chemlab/hx')
  const sheet = page.locator('section', { has: page.getByRole('heading', { name: 'Drawing (2D, first-angle)' }) })
  await expect(sheet).toBeVisible({ timeout: 180_000 })
  await expect(sheet.locator('svg')).toContainText('SECTION C–C (TUBE BUNDLE, 28 TUBES, 2:1)') // template defaults
  await expect(sheet.locator('svg circle.tube')).toHaveCount(28)
  const chart = page.locator('figure', { hasText: 'Counter-flow temperature profile' })
  await expect(chart.locator('polyline')).toHaveCount(2) // hot and cold
  await expect(sheet.getByRole('button', { name: 'Download SVG of the drawing', exact: true })).toBeVisible()
})

test('ChemLab heat exchanger tab says why there is no drawing when a 1-2 exchanger cannot do the duty', async ({ page }) => {
  // the hx template returns ok with no geometry here: the cold outlet would cross the hot outlet
  await page.goto('/#chemlab/hx?mh=1&cph=4000&Th_in=400&Th_out=300&mc=1&cpc=4000&Tc_in=290')
  await expect(page.getByText('No exchanger drawing: a 1-2 shell-and-tube exchanger cannot do this duty', { exact: false })).toBeVisible({ timeout: 180_000 })
  await expect(page.getByText('a 1-2 shell-and-tube exchanger cannot do this duty (temperature cross)')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Drawing (2D, first-angle)' })).toHaveCount(0)
})

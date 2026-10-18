import { expect, test } from '@playwright/test'
import { columnViews } from '../src/chemlab/drawings/column.ts'

const inputs = Object.fromEntries(
  ['F', 'zF', 'xD', 'xB', 'q', 'alpha', 'R', 'R_factor', 'Eo', 'P', 'T_top', 'MW_top', 'rho_L'].map((k, i) => [k, { value: i + 1, unit: '-' }]),
)
// McCabe-Thiele defaults: D 1.017 m, 19 real trays at 0.6 m, feed on tray 10
const col = (D = 1.0169, nT = 19, f = 10) => columnViews({ diameter_m: D, height_m: nT * 0.6, n_trays: nT, feed_tray: f }, inputs)
const count = (s: string, re: RegExp) => (s.match(re) ?? []).length

test('column drawing: views, dimensions and trays come from the template geometry', () => {
  const s = col()
  for (const t of ['FRONT ELEVATION', 'SECTION B–B', 'FIRST ANGLE PROJECTION', 'D = 1017 mm', 'H = 11400 mm (tangent to tangent)',
    'Feed (tray 10)', 'Tray 1 (top)', 'Tray 19 (bottom)', '19 real trays, spacing 600 mm; feed on tray 10.', 'rho_L = 13 -'])
    expect(s).toContain(t)
  expect(count(s, /class="tray"/g) + count(s, /class="feed"/g)).toBe(19) // every tray drawn at this spacing
  expect(count(s, /class="feed"/g)).toBe(1)
  expect(count(s, /<line class="o" /g)).toBe(19) // one downcomer under each tray, the last one into the sump
  expect(s).not.toContain('width drawn') // a 1 m column fits at true proportions
})

test('column drawing: tall thin columns say what is exaggerated or thinned out', () => {
  const s = col(0.032, 192, 97)
  expect(s).toContain('width drawn ×')
  expect(s).toContain('1 tray in ')
  const drawn = count(s, /class="tray"/g) + count(s, /class="feed"/g)
  expect(drawn).toBeLessThan(192)
  expect(drawn).toBeGreaterThan(40)
  expect(s).toContain('Feed (tray 97)') // the feed tray is always drawn and labelled
})

test('column drawing: edge cases', () => {
  expect(columnViews({ diameter_m: 1, height_m: 0, n_trays: 0, feed_tray: 1 }, inputs)).toBe('') // reboiler only
  expect(col(1, 19, 25)).toContain('Feed (tray 19)') // feed clamped onto a real tray
  expect(col(0.5, 1, 1)).toContain('1 real tray, spacing 600 mm')
})

test('column drawing: valid references, unique ids, nothing past the sheet border', () => {
  const sweep = [col(), col(0.032, 192, 97), col(10.17, 19, 10), col(0.5, 1, 1), col(1.0169, 19, 1), col(1.0169, 19, 19), col(2.4, 3980, 1990)]
  const ids = sweep.flatMap((s) => [...s.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]))
  expect(new Set(ids).size).toBe(ids.length)
  for (const s of sweep) {
    for (const [, ref] of s.matchAll(/url\(#([^)]+)\)/g)) expect(s).toContain(`id="${ref}"`)
    // rough text extent at 11 px Arial (about 6 px a character) must stay inside the 10..990 frame
    for (const [, x, anchor, attrs, body] of s.matchAll(/<text x="([\d.-]+)" y="[\d.-]+" text-anchor="(\w+)"([^>]*)>([^<]*)</g)) {
      if (attrs.includes('rotate')) continue // vertical dimension text runs along y, not x
      const w = body.length * 6, x0 = +x - (anchor === 'end' ? w : anchor === 'middle' ? w / 2 : 0)
      expect(x0, body).toBeGreaterThanOrEqual(12)
      expect(x0 + w, body).toBeLessThanOrEqual(988)
    }
  }
})

test('column drawing: geometry is finite, inside the sheet, and section B-B matches the elevation', () => {
  for (const [D, nT, f] of [[1.0169, 19, 10], [0.032, 192, 97], [10.17, 19, 10], [0.5, 1, 1], [1.0169, 19, 1], [1.0169, 19, 19], [2.4, 3980, 1990], [1.0169, 2, 2]]) {
    const s = col(D, nT, f)
    expect(s).not.toContain('NaN')
    expect(s).toMatch(/Elevation approx\. (1:\d+|[\d.]+:1) at 1000 mm sheet width/) // the scale says what it assumes
    for (const [, a, v] of s.matchAll(/\b(x|x1|x2|cx|y|y1|y2|cy)="(-?[\d.]+)"/g)) {
      const lim = a.startsWith('x') || a === 'cx' ? 1000 : 700
      expect(+v, `${a}=${v} (D ${D}, ${nT} trays)`).toBeGreaterThanOrEqual(0)
      expect(+v, `${a}=${v} (D ${D}, ${nT} trays)`).toBeLessThanOrEqual(lim)
    }
    const m = +/SECTION B–B \(TRAY (\d+) DECK/.exec(s)![1]
    // outlet weir: the vertical o2 line inside the section circle (cx 780) lies on the side the elevation shows
    const weir = [...s.matchAll(/<line class="o2" x1="([\d.]+)" y1="[\d.]+" x2="([\d.]+)"/g)].map((r) => [+r[1], +r[2]]).filter(([a, b]) => a === b && Math.abs(a - 780) < 80)
    expect(weir.length).toBe(1)
    expect(m % 2 ? weir[0][0] > 780 : weir[0][0] < 780).toBe(true)
    expect(s).toContain(m === 1 ? 'Inlet (reflux)' : '>Inlet<')
    if (m === nT) expect(s).toContain('Downcomer to sump')
  }
})

test('ChemLab McCabe-Thiele tab shows the column drawing from the real template', async ({ page }) => {
  await page.goto('/#chemlab/mccabe')
  const sheet = page.locator('section', { has: page.getByRole('heading', { name: 'Drawing (2D, first-angle)' }) })
  await expect(sheet).toBeVisible({ timeout: 180_000 })
  await expect(sheet.locator('svg')).toContainText('FRONT ELEVATION')
  await expect(sheet.locator('svg')).toContainText('Feed (tray 10)') // matches the template's geometry above
  await expect(sheet.getByRole('button', { name: 'Download SVG of the drawing', exact: true })).toBeVisible()
})

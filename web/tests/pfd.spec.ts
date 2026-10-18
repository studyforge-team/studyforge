import { expect, test } from '@playwright/test'
import { pfd, SYMBOLS } from '../src/chemlab/drawings/pfd.ts'

const TEMPLATES = ['cstr', 'batch', 'pfr', 'mccabe', 'hx', 'flash', 'recycle', 'pipe']
// unit tags and stream names each flowsheet must show
const EXPECT: Record<string, string[]> = {
  cstr: ['R-101', 'P-101', 'E-101', 'Feed', 'Product', 'Coolant in', 'Coolant out'],
  batch: ['R-101', 'FV-101', 'P-101', 'Charge', 'Product'],
  pfr: ['R-101', 'E-101', 'P-101', 'Feed', 'Product', 'Coolant in'],
  mccabe: ['T-101', 'E-101', 'E-102', 'E-103', 'V-101', 'P-101', 'Feed', 'Distillate', 'Bottoms', 'Reflux', 'Coolant in', 'Steam'],
  hx: ['E-101', 'FV-101', 'P-101', 'Hot fluid in', 'Hot fluid out', 'Cold fluid in', 'Cold fluid out'],
  flash: ['V-101', 'E-101', 'FV-101', 'P-101', 'Feed', 'Vapour', 'Liquid'],
  recycle: ['M-101', 'R-101', 'V-101', 'S-101', 'Fresh feed', 'Recycle', 'Purge', 'Product'],
  pipe: ['TK-101', 'TK-102', 'P-101', 'FV-101', 'Suction', 'Discharge'],
}

test('pfd: every template is a well-formed SVG with its tags and stream names', () => {
  for (const t of TEMPLATES) {
    const s = pfd(t)!
    expect(s, t).toMatch(/^<svg [^>]*viewBox="0 0 1000 420"/)
    expect(s.trim().endsWith('</svg>'), t).toBe(true)
    expect(s).not.toContain('NaN')
    for (const w of EXPECT[t]) expect(s, `${t}: ${w}`).toContain(`>${w}<`)
    expect((s.match(/<svg/g) ?? []).length).toBe(1)
    expect((s.match(/<g[ >]/g) ?? []).length).toBe((s.match(/<\/g>/g) ?? []).length) // balanced groups
    for (const [, ref] of s.matchAll(/url\(#([^)]+)\)/g)) expect(s).toContain(`id="${ref}"`) // arrowhead marker exists
    expect(s).toContain('marker-end')
  }
})

test('pfd: unknown templates give null, including prototype names', () => {
  for (const t of ['', 'nope', 'toString', '__proto__', 'constructor', 'CSTR']) expect(pfd(t)).toBeNull()
})

test('pfd: recycle flowsheet shows mixer, reactor, separator, splitter, recycle and purge', () => {
  const s = pfd('recycle')!
  for (const w of ['Recycle', 'Purge', 'M-101', 'R-101', 'V-101', 'S-101', 'Mixer', 'Splitter']) expect(s).toContain(w)
  // the recycle line is the only path that returns to the mixer (x = 200): it ends there pointing down
  expect(s).toMatch(/d="M720 115L720 60L200 60L200 195"/)
})

test('pfd: 12 symbols listed, tee drawn, no numeric process values, no script, nothing raw', () => {
  expect(SYMBOLS.length).toBe(12)
  for (const t of TEMPLATES) {
    const s = pfd(t)!
    expect(s.toLowerCase()).not.toContain('<script')
    expect(s).not.toMatch(/\bon\w+=/)
    // every text node is a tag (X-101), a stream name, or the fixed note: never a number with a unit
    for (const [, body] of s.matchAll(/<text[^>]*>([^<]*)</g))
      expect(body, `${t}: ${body}`).not.toMatch(/\d+(\.\d+)?\s*(K|Pa|kg|m|s|W|kmol|mol|%|bar)\b/)
  }
  const all = TEMPLATES.map((t) => pfd(t)!).join('')
  expect(all).toContain('class="dot"') // tee
})

test('pfd: text is escaped and unique ids per call', () => {
  const a = pfd('cstr')!, b = pfd('cstr')!
  const id = (s: string) => /<marker id="([^"]+)"/.exec(s)![1]
  expect(id(a)).not.toBe(id(b))
  for (const t of TEMPLATES) expect(pfd(t)!).not.toMatch(/<text[^>]*>[^<]*[&](?!amp;|lt;|gt;)/)
})

// ChemLab only has tabs for cstr, batch, pfr, mccabe and hx; flash, recycle and pipe have no page yet.
for (const [tab, tags] of [['cstr', ['R-101', 'Coolant in']], ['mccabe', ['T-101', 'Distillate']], ['hx', ['E-101', 'Hot fluid in']]] as const) {
  test(`ChemLab ${tab} tab shows the process flow diagram`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 800 })
    await page.goto(`/#chemlab/${tab}`)
    const sec = page.locator('section', { has: page.getByRole('heading', { name: 'Process flow diagram' }) })
    await expect(sec).toBeVisible({ timeout: 180_000 })
    await expect(sec.locator('svg')).toHaveCount(1)
    for (const t of tags) await expect(sec.locator('svg')).toContainText(t)
    await expect(sec.getByRole('button', { name: 'Download SVG of the process flow diagram', exact: true })).toBeVisible()
    if (tab === 'cstr') { // WCAG 2.4.6: the PFD and Drawing download buttons need distinct accessible names
      await expect(page.getByRole('button', { name: 'Download SVG of the drawing', exact: true })).toHaveCount(1)
      await expect(page.getByRole('button', { name: /^Download SVG/ })).toHaveCount(2)
    }
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(over).toBeLessThanOrEqual(0) // no horizontal page scroll at 375 px
  })
}

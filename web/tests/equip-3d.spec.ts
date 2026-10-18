import { expect, test, type Page } from '@playwright/test'

const T = { timeout: 180_000 }
const view = (page: Page) => page.locator('section').filter({ has: page.getByRole('heading', { name: '3D view' }) })
const canvas = (page: Page) => view(page).locator('canvas')
const tris = async (page: Page) => { await expect.poll(async () => +((await canvas(page).getAttribute('data-tris')) ?? 0), T).toBeGreaterThan(0); return +(await canvas(page).getAttribute('data-tris'))! }

test('column: 3D view labelled with the real tray count, within the triangle budget', async ({ page }) => {
  await page.goto('/#chemlab/mccabe')
  const n = /(\d+) real trays?/.exec(await page.locator('svg').filter({ hasText: 'FRONT ELEVATION' }).textContent({ timeout: 180_000 }) ?? '')![1]
  await expect(canvas(page)).toHaveAttribute('aria-label', new RegExp(`${n} real trays`), T)
  const t = await tris(page)
  expect(t).toBeLessThanOrEqual(30000)
  await expect(canvas(page)).toHaveAttribute('data-instances', n)
  await expect(view(page)).not.toContainText('diameter drawn ×')
  await view(page).screenshot({ path: 'C:/Claudecode/sf-wt/v3db-column.png' })
})

test('hx: defaults (28 tubes) within budget, no subset label', async ({ page }) => {
  await page.goto('/#chemlab/hx')
  const t = await tris(page)
  expect(t).toBeLessThanOrEqual(30000)
  await expect(canvas(page)).toHaveAttribute('aria-label', /28 tubes/)
  await expect(page.getByText(/Showing \d+ of/)).toHaveCount(0)
  await expect(view(page)).toContainText('diameter drawn ×6.9 for clarity')
  await view(page).screenshot({ path: 'C:/Claudecode/sf-wt/v3db-hx.png' })
})

test('hx: a huge bundle draws a capped subset and labels the real count', async ({ page }) => {
  await page.goto('/#chemlab/hx?mh=1000&mc=1250') // ~12000 tubes at the default tube size
  await expect(page.getByText(/Showing \d+ of \d{4,} tubes/)).toBeVisible(T)
  expect(await tris(page)).toBeLessThanOrEqual(30000)
})

test('WebGL missing: text fallback, 2D drawing still there', async ({ page }) => {
  await page.addInitScript(() => {
    const g = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, t: string, ...a: unknown[]) {
      return /webgl/.test(t) ? null : (g as (...x: unknown[]) => RenderingContext | null).call(this, t, ...a)
    } as typeof g
  })
  await page.goto('/#chemlab/hx')
  await expect(page.getByText("3D isn't available on this device — see the 2D drawing below.")).toBeVisible(T)
  await expect(page.getByRole('heading', { name: 'Drawing (2D, first-angle)' })).toBeVisible()
})

test('the 3D chunk is not loaded on the dashboard', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const names = await page.evaluate(() => performance.getEntriesByType('resource').map((r) => r.name))
  expect(names.filter((u) => /Equip3D|Cstr3D|OrbitControls|three/i.test(u))).toEqual([])
})

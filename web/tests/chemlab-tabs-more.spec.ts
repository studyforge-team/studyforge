import { expect, test } from '@playwright/test'

// ChemLab tabs for the flash, recycle and pipe templates (no engineering drawing sheet for these).
const TABS = [
  { id: 'flash', label: 'Flash drum', tags: ['V-101', 'Feed', 'Vapour', 'Liquid'], chart: 'T-x-y diagram' },
  { id: 'recycle', label: 'Recycle loop', tags: ['M-101', 'Recycle', 'Purge'], chart: 'Overall conversion vs purge fraction' },
  { id: 'pipe', label: 'Pipe and pump', tags: ['TK-101', 'P-101', 'Suction'], chart: 'System curve: head vs flow' },
]

for (const tab of TABS) {
  test(`ChemLab ${tab.id} tab: outputs, PFD, plot, no overflow, no console errors`, async ({ page }) => {
    const errors: string[] = []
    page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()) })
    page.on('pageerror', (e) => errors.push(String(e)))
    await page.setViewportSize({ width: 375, height: 800 })

    // reachable by clicking the tab from another one
    await page.goto('/#chemlab/cstr')
    const btn = page.getByRole('button', { name: tab.label, exact: true })
    await btn.click({ timeout: 180_000 }) // the tabs appear once Python has started
    await expect(btn).toHaveAttribute('aria-pressed', 'true', { timeout: 180_000 })
    // and by URL
    await page.goto(`/#chemlab/${tab.id}`)
    await page.reload()
    await expect(btn).toHaveAttribute('aria-pressed', 'true', { timeout: 180_000 })

    const op = page.locator('section', { has: page.getByRole('heading', { name: 'Operating point' }) })
    await expect(op).toBeVisible({ timeout: 180_000 })
    expect(await op.locator('[data-out]').count()).toBeGreaterThan(0)

    const sec = page.locator('section', { has: page.getByRole('heading', { name: 'Process flow diagram' }) })
    await expect(sec).toBeVisible()
    await expect(sec.locator('svg')).toHaveCount(1)
    for (const t of tab.tags) await expect(sec.locator('svg')).toContainText(t)

    await expect(page.getByRole('img', { name: tab.chart })).toBeVisible()
    await expect(page.getByRole('heading', { name: /Drawing \(2D/ })).toHaveCount(0)
    await expect(page.getByRole('alert').filter({ hasText: /\S/ })).toHaveCount(0)

    const text = await page.locator('main').innerText()
    for (const bad of ['NaN', 'undefined', 'Infinity']) expect(text).not.toContain(bad)

    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(over).toBeLessThanOrEqual(0)
    expect(errors).toEqual([])

    await page.screenshot({ path: `${process.env.SHOTS ?? 'test-results'}/${tab.id}.png`, fullPage: true })
  })
}

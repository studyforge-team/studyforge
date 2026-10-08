import { expect, test } from '@playwright/test'

const Q = 'CSTR first-order reaction, k = 0.2 1/min, tau = 10 min. Find conversion.'
const sizes = [{ width: 375, height: 812 }, { width: 1280, height: 800 }]

for (const vp of sizes) {
  test(`solve flow at ${vp.width}px`, async ({ page }) => {
    const csp: string[] = []
    page.on('console', (m) => { if (/content security policy|refused to/i.test(m.text())) csp.push(m.text()) })
    await page.setViewportSize(vp)
    await page.goto('/')
    await page.getByLabel('Your question').fill(Q)
    await page.getByRole('button', { name: 'Solve' }).click()
    const card = page.getByRole('region', { name: 'Answer' })
    await expect(card).toBeVisible({ timeout: 120_000 })
    await expect(card.locator('.katex').first()).toBeAttached()
    await expect(card.getByRole('img', { name: 'Figure 1' })).toBeVisible()
    await expect(card.getByTestId('confidence')).toHaveText('high')
    expect(await card.innerText()).toMatch(/0\.667|66\.7/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(card.getByTestId('diagram').locator('svg')).toBeVisible()
    await expect(card.getByTestId('diagram')).toContainText('CSTR')
    expect(csp).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('failed code shows Not verified', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your question').fill('please fail')
  await page.getByRole('button', { name: 'Solve' }).click()
  await expect(page.getByText('Not verified — check this answer')).toBeVisible({ timeout: 120_000 })
})

test('confirm shows the confirm box', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your question').fill('please confirm')
  await page.getByRole('button', { name: 'Solve' }).click()
  await expect(page.getByText('Confirm screen (S5) goes here')).toBeVisible()
})

test('mermaid chunk is not loaded before solving', async ({ page }) => {
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  const names = await page.evaluate(() => performance.getEntriesByType('resource').map((e) => e.name))
  expect(names.filter((n) => /mermaid|Diagram/i.test(n))).toEqual([])
})

test('bad mermaid falls back to a code block', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your question').fill('baddiagram please')
  await page.getByRole('button', { name: 'Solve' }).click()
  const card = page.getByRole('region', { name: 'Answer' })
  await expect(card.getByText("Diagram couldn't be drawn — here is its source.")).toBeVisible({ timeout: 120_000 })
  await expect(card.locator('pre code').filter({ hasText: 'flowchart LR' })).toBeVisible()
  await expect(card.getByTestId('diagram')).toHaveCount(0)
})

test('print media shows the answer only; Download PDF on screen', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('Your question').fill(Q)
  await page.getByRole('button', { name: 'Solve' }).click()
  const card = page.getByRole('region', { name: 'Answer' })
  await expect(card.getByTestId('diagram').locator('svg')).toBeVisible({ timeout: 120_000 })
  await expect(card.getByRole('button', { name: 'Download PDF' })).toBeVisible()
  await page.emulateMedia({ media: 'print' })
  await expect(page.getByLabel('Your question')).toBeHidden()
  await expect(page.getByRole('button', { name: 'Solve' })).toBeHidden()
  await expect(card.getByRole('button', { name: 'Download PDF' })).toBeHidden()
  await expect(card).toBeVisible()
  await expect(card.getByRole('img', { name: 'Figure 1' })).toBeVisible()
  await expect(page.locator('p', { hasText: Q })).toBeVisible()
})

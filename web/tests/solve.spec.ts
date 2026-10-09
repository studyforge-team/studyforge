import { expect, test } from '@playwright/test'

const Q = 'CSTR first-order reaction, k = 0.2 1/min, tau = 10 min. Find conversion.'
const sizes = [{ width: 375, height: 812 }, { width: 1280, height: 800 }]

for (const vp of sizes) {
  test(`solve flow at ${vp.width}px`, async ({ page }) => {
    const csp: string[] = []
    page.on('console', (m) => { if (/content security policy|refused to/i.test(m.text())) csp.push(m.text()) })
    await page.setViewportSize(vp)
    await page.goto('/#solve')
    await page.getByLabel('Your question').fill(Q)
    await page.getByRole('button', { name: 'Solve' }).click()
    const card = page.getByRole('region', { name: 'Answer' })
    await expect(card).toBeVisible({ timeout: 120_000 })
    await expect(card.locator('.katex').first()).toBeAttached()
    await expect(card.getByRole('img', { name: 'Figure 1' })).toBeVisible()
    await expect(card.getByTestId('confidence')).toHaveText('high')
    await expect(card.getByText('Computed in your browser')).toBeVisible()
    expect(await card.innerText()).toMatch(/0\.667|66\.7/)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect(card.getByTestId('diagram').locator('svg')).toBeVisible()
    await expect(card.getByTestId('diagram')).toContainText('CSTR')
    expect(csp).toEqual([])
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('failed code shows Not verified', async ({ page }) => {
  await page.goto('/#solve')
  await page.getByLabel('Your question').fill('please fail')
  await page.getByRole('button', { name: 'Solve' }).click()
  await expect(page.getByText('Not verified — check this answer')).toBeVisible({ timeout: 120_000 })
  await expect(page.getByText('Computed in your browser')).toHaveCount(0)
})

test('unknown question gets an honest demo-mode answer at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#solve')
  await page.getByLabel('Your question').fill('Hot oil is cooled from 150°C to 90°C in a counter-current heat exchanger; find the LMTD.')
  await page.getByRole('button', { name: 'Solve' }).click()
  const card = page.getByRole('region', { name: 'Answer' })
  await expect(card.getByText("your question wasn't read")).toBeVisible({ timeout: 120_000 })
  await expect(card.getByText('Confidence: low')).toBeVisible()
  await expect(page.getByText('Computed in your browser')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('confirm shows the confirm box', async ({ page }) => {
  await page.goto('/#solve')
  await page.getByLabel('Your question').fill('please confirm')
  await page.getByRole('button', { name: 'Solve' }).click()
  await expect(page.getByText('Confirm screen (S5) goes here')).toBeVisible()
})

test('mermaid chunk is not loaded before solving', async ({ page }) => {
  await page.goto('/#solve')
  await page.waitForLoadState('networkidle')
  const names = await page.evaluate(() => performance.getEntriesByType('resource').map((e) => e.name))
  expect(names.filter((n) => /mermaid|Diagram/i.test(n))).toEqual([])
})

test('bad mermaid falls back to a code block', async ({ page }) => {
  await page.goto('/#solve')
  await page.getByLabel('Your question').fill('baddiagram CSTR please')
  await page.getByRole('button', { name: 'Solve' }).click()
  const card = page.getByRole('region', { name: 'Answer' })
  await expect(card.getByText("Diagram couldn't be drawn — here is its source.")).toBeVisible({ timeout: 120_000 })
  await expect(card.locator('pre code').filter({ hasText: 'flowchart LR' })).toBeVisible()
  await expect(card.getByTestId('diagram')).toHaveCount(0)
})

test('print media shows the answer only; Download PDF on screen', async ({ page }) => {
  await page.goto('/#solve')
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

const PNG = { name: 'q.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgo=', 'base64') }

test('attach: demo mode says the file was not read; chip can be removed', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#solve')
  await page.locator('input[type=file]').setInputFiles(PNG)
  await expect(page.getByText("Demo mode — your file wasn't read.")).toBeVisible()
  await expect(page.getByRole('button', { name: 'Use this text' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Solve' })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Remove attachment' }).click()
  await expect(page.getByRole('button', { name: 'Remove attachment' })).toHaveCount(0)
  await expect(page.getByText("Demo mode — your file wasn't read.")).toHaveCount(0)
})

test('attach: file over 10 MB is rejected with no request', async ({ page }) => {
  const reqs: string[] = []
  page.on('request', (r) => { if (r.method() === 'POST') reqs.push(r.url()) })
  await page.goto('/#solve')
  await page.locator('input[type=file]').setInputFiles({ name: 'big.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(11 * 1024 * 1024) })
  await expect(page.getByRole('alert')).toHaveText('That file is over 10 MB. Try a smaller PDF or a cropped photo.')
  await expect(page.getByRole('button', { name: 'Remove attachment' })).toHaveCount(0)
  expect(reqs).toEqual([])
})

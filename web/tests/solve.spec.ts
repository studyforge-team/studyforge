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

async function openConfirm(page: import('@playwright/test').Page, text = 'please confirm cstr k = 0.2 1/min tau = 10 min') {
  await page.goto('/#solve')
  await page.getByLabel('Your question').fill(text)
  await page.getByRole('button', { name: 'Solve', exact: true }).click()
  const box = page.getByLabel('Question as we read it')
  await expect(page.getByRole('heading', { name: 'Check the question before solving' })).toBeVisible()
  return box
}

test('confirm card: edit then approve runs the normal solve', async ({ page }) => {
  const box = await openConfirm(page)
  await expect(box).toHaveValue('please confirm cstr k = 0.2 1/min tau = 10 min')
  await expect(box).toBeEditable()
  await box.fill(Q)
  await page.getByRole('button', { name: 'Solve this question' }).click()
  const card = page.getByRole('region', { name: 'Answer' })
  await expect(card).toBeVisible({ timeout: 120_000 })
  await expect(card.getByTestId('confidence')).toHaveText('high')
  expect(await card.innerText()).toMatch(/0\.667|66\.7/)
  await expect(page.getByRole('heading', { name: 'Check the question before solving' })).toHaveCount(0)
  await expect(page.getByLabel('Your question')).toHaveValue(Q)
})

test('confirm card: Type it myself dismisses; blank text disables Solve this question', async ({ page }) => {
  const box = await openConfirm(page)
  const go = page.getByRole('button', { name: 'Solve this question' })
  await box.fill('   ')
  await expect(go).toBeDisabled()
  await box.fill('x')
  await expect(go).toBeEnabled()
  await page.getByRole('button', { name: 'Type it myself' }).click()
  await expect(page.getByRole('heading', { name: 'Check the question before solving' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Answer' })).toHaveCount(0)
})

test('confirm card fits at 375px', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await openConfirm(page)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= 375)).toBe(true)
  for (const n of ['Solve this question', 'Type it myself']) {
    const bb = await page.getByRole('button', { name: n }).boundingBox()
    expect(bb!.height).toBeGreaterThanOrEqual(44)
  }
})

test('demo mode: attaching a file shows the plain empty-text error, no confirm card', async ({ page }) => {
  await page.goto('/#solve')
  await page.locator('input[type=file]').first().setInputFiles({ name: 'q.png', mimeType: 'image/png', buffer: Buffer.from('x') })
  await expect(page.getByRole('alert')).toContainText("Demo mode doesn't read photos")
  await expect(page.getByRole('heading', { name: 'Check the question before solving' })).toHaveCount(0)
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

test('attach: file over 10 MB is rejected with no request', async ({ page }) => {
  const reqs: string[] = []
  page.on('request', (r) => { if (r.method() === 'POST') reqs.push(r.url()) })
  await page.goto('/#solve')
  await page.locator('input[type=file]').setInputFiles({ name: 'big.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(11 * 1024 * 1024) })
  await expect(page.getByRole('alert')).toHaveText('That file is over 10 MB. Try a smaller PDF or a cropped photo.')
  await expect(page.getByRole('button', { name: 'Remove attachment' })).toHaveCount(0)
  expect(reqs).toEqual([])
})

test('unreadable photo shows a plain message and is not attached', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#solve')
  await page.locator('input[type=file]').setInputFiles(PNG) // demo mock reads every upload as empty text
  await expect(page.getByRole('alert')).toHaveText("Demo mode doesn't read photos or PDFs yet. Type the question instead.")
  await expect(page.getByRole('button', { name: 'Remove attachment' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Solve' })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

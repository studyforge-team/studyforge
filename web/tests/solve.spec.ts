import { expect, test } from '@playwright/test'

const Q = 'CSTR first-order reaction, k = 0.2 1/min, tau = 10 min. Find conversion.'
const sizes = [{ width: 375, height: 812 }, { width: 1280, height: 800 }]

for (const vp of sizes) {
  test(`solve flow at ${vp.width}px`, async ({ page }) => {
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

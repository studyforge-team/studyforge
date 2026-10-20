import { expect, test, type Page } from '@playwright/test'

const noOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test.describe('Interview Bank Page', () => {
  test('Field switch toggles between Chemical and Computer science', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#interview')

    // Default is Chemical
    await expect(
      page.getByRole('heading', { name: 'Chemical Company Interview Prep' }),
    ).toBeVisible()

    // Switch to Computer science
    await page.getByRole('button', { name: 'Computer science' }).click()
    await expect(
      page.getByRole('heading', { name: 'Computer Science Interview Bank' }),
    ).toBeVisible()
    await expect(page.getByText('LRU Cache Design')).toBeVisible()
    await expect(page.getByText('Distributed Rate Limiter')).toBeVisible()

    // Switch back to Chemical
    await page.getByRole('button', { name: 'Chemical' }).click()
    await expect(
      page.getByRole('heading', { name: 'Chemical Company Interview Prep' }),
    ).toBeVisible()

    expect(await noOverflow(page)).toBe(true)
  })
})

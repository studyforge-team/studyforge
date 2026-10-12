
import { expect, test } from '@playwright/test'

test('Time-to-Finish page is reachable from main navigation', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Main' })
  await nav.getByRole('link', { name: 'Time to Finish' }).click()

  await expect(
    page.getByRole('heading', { name: 'Time to Finish' }),
  ).toBeVisible()
  await expect(page.getByLabel(/number of pages/i)).toBeVisible()
})

test('shows a time range for a 30-page document', async ({ page }) => {
  await page.goto('/#time-to-finish')
  await page.getByLabel(/number of pages/i).fill('30')

  await expect(page.getByRole('region', { name: /estimate/i })).toBeVisible()
  await expect(page.getByRole('region', { name: /estimate/i })).toContainText(
    /minutes|hours/i,
  )
  await expect(page.getByText(/rough estimate|approximation/i)).toBeVisible()
})

test('rejects invalid page counts', async ({ page }) => {
  await page.goto('/#time-to-finish')
  const pages = page.getByLabel(/number of pages/i)

  await pages.fill('0')
  await expect(page.getByRole('alert')).toBeVisible()

  await pages.fill('-2')
  await expect(page.getByRole('alert')).toBeVisible()
})

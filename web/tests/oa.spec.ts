import { expect, test, type Page } from '@playwright/test'

const noOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test.describe('OA Coding Practice', () => {
  test('Coding tab shows existing problems and has no horizontal scroll at 375px', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa')
    await expect(page.getByRole('heading', { name: 'Coding Practice' })).toBeVisible()
    await expect(
      page.getByText('Calculate CSTR Residence Time Distribution'),
    ).toBeVisible()
    await expect(page.getByText('Antoine Equation Vapor Pressure Solver')).toBeVisible()
    expect(await noOverflow(page)).toBe(true)
  })
})

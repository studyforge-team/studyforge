import { expect, test } from '@playwright/test'

test('PYQ Predictor builds a frequency table from three papers', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#pyq-predictor')

  await expect(page.getByRole('heading', { name: 'PYQ Predictor' })).toBeVisible()

  await page.getByLabel('Past paper 1').fill(
    'Binary search. Arrays. Binary search.',
  )
  await page.getByLabel('Past paper 2').fill(
    'Binary search. Linked lists.',
  )
  await page.getByLabel('Past paper 3').fill(
    'Arrays. Binary search.',
  )

  await page.getByRole('button', { name: 'Predict topics' }).click()

  const results = page.getByRole('table', { name: 'Topic frequency' })
  await expect(results).toBeVisible()
  await expect(results).toContainText('Binary search')
  await expect(results).toContainText('3')
  await expect(page.getByRole('heading', { name: 'Likely practice paper' })).toBeVisible()
  await expect(page.getByText(/not guaranteed/i)).toBeVisible()
})

test('PYQ Predictor asks for all three papers before predicting', async ({ page }) => {
  await page.goto('/#pyq-predictor')

  await page.getByLabel('Past paper 1').fill('Binary search and arrays')
  await page.getByRole('button', { name: 'Predict topics' }).click()

  await expect(page.getByRole('alert')).toContainText(/three past papers/i)
  await expect(page.getByRole('table', { name: 'Topic frequency' })).toHaveCount(0)
})

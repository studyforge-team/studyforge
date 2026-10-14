import { expect, test, type Page } from '@playwright/test'

async function open(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.getByRole('region', { name: 'Reminders inbox' }).getByRole('link', { name: 'Answer the check-in' }).click()
  await expect(page).toHaveURL(/checkin=1234567890/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Check-in: Heat transfer quiz')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

test('correct answer marks the task done', async ({ page }) => {
  await open(page)
  await page.getByLabel('Equal to the outlet concentration').check()
  await page.getByRole('button', { name: 'Check' }).click()
  await expect(page.getByText('Correct.')).toBeVisible()
  await expect(page.getByText('Marked done')).toBeVisible()
})

test('wrong answer schedules a follow-up', async ({ page }) => {
  await open(page)
  await page.getByLabel('Equal to the inlet concentration').check()
  await page.getByRole('button', { name: 'Check' }).click()
  await expect(page.getByText('Incorrect')).toBeVisible()
  await expect(page.getByText("We'll check in again")).toBeVisible()
})

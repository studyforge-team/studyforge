import { expect, test } from '@playwright/test'

test('a reminder link opens its prep pack: task, quiz and the notes page of a question', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#prep/0123456789abcdef')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Prep pack')
  await expect(page.getByText(/CRE assignment 3 — CSTR design · due /)).toBeVisible()
  await expect(page.getByRole('button', { name: 'From your notes: page 2' })).toBeVisible({ timeout: 180_000 }) // after the sandbox checks the keys
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('only 16-hex task keys are prep packs', async ({ page }) => {
  await page.goto('/#prep/not-a-key')
  await expect(page.getByRole('heading', { level: 1 })).not.toContainText('Prep pack')
})

test('the Quiz page itself is unchanged: no prep heading, no notes links', async ({ page }) => {
  await page.goto('/#quiz')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Quiz')
  await expect(page.getByRole('heading', { level: 1 })).not.toContainText('Prep pack')
  await expect(page.getByRole('button', { name: /From your notes/ })).toHaveCount(0)
})

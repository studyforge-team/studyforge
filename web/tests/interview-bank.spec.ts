import { expect, test } from '@playwright/test'

test('Interview Bank filters questions by company', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#interview-bank')

  await expect(page.getByRole('heading', { name: 'Interview Bank' })).toBeVisible()

  const company = page.getByLabel('Filter by company')
  await company.selectOption('Google')

  const questions = page.getByRole('list', { name: 'Practice questions' })
  await expect(questions).toContainText('Google')
  await expect(questions).not.toContainText('Microsoft')
})

test('answers stay hidden until revealed', async ({ page }) => {
  await page.goto('/#interview-bank')

  const questions = page.getByRole('list', { name: 'Practice questions' })
  const firstQuestion = questions.getByRole('listitem').first()

  await expect(firstQuestion.getByText('Answer:', { exact: false })).toHaveCount(0)
  await firstQuestion.getByRole('button', { name: 'Show answer' }).click()
  await expect(firstQuestion.getByText('Answer:', { exact: false })).toBeVisible()
})

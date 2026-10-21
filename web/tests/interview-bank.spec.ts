import { expect, test } from '@playwright/test'

test('Interview Bank filters questions by company', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#interview-bank')
  await page.getByRole('button', { name: 'Computer science', exact: true }).click() // FO2: Chemical is the default field

  await expect(page.getByRole('heading', { name: 'Interview Bank' })).toBeVisible()

  const company = page.getByLabel('Filter by company')
  await company.selectOption('Google')

  const questions = page.getByRole('list', { name: 'Practice questions' })
  await expect(questions).toContainText('Google')
  await expect(questions).not.toContainText('Microsoft')
})

test('answers stay hidden until revealed', async ({ page }) => {
  await page.goto('/#interview-bank')
  await page.getByRole('button', { name: 'Computer science', exact: true }).click() // FO2: Chemical is the default field

  const questions = page.getByRole('list', { name: 'Practice questions' })
  const firstQuestion = questions.getByRole('listitem').first()

  await expect(firstQuestion.getByText('Answer:', { exact: false })).toHaveCount(0)
  await firstQuestion.getByRole('button', { name: 'Show answer' }).click()
  await expect(firstQuestion.getByText('Answer:', { exact: false })).toBeVisible()
})

test('interview bank says the questions are illustrative, not real company questions', async ({ page }) => {
  await page.goto('/#interview-bank')
  await page.getByRole('button', { name: 'Computer science', exact: true }).click() // FO2: Chemical is the default field
  await expect(page.getByTestId('ib-disclaimer')).toContainText('not actual questions')
})

test('interview bank: hide answer again, and the first option shows every company', async ({ page }) => {
  await page.goto('/#interview-bank')
  await page.getByRole('button', { name: 'Computer science', exact: true }).click() // FO2: Chemical is the default field
  const questions = page.getByRole('list', { name: /questions/i })
  const first = questions.getByRole('listitem').first()
  const toggle = first.getByRole('button', { name: 'Show answer' })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await toggle.click()
  const hide = first.getByRole('button', { name: 'Hide answer' })
  await expect(hide).toHaveAttribute('aria-expanded', 'true')
  await hide.click()
  await expect(first.getByText('Answer:', { exact: false })).toHaveCount(0)

  const company = page.locator('select')
  const all = await questions.getByRole('listitem').count()
  await company.selectOption('Google')
  const google = await questions.getByRole('listitem').count()
  expect(google).toBeGreaterThan(0)
  expect(google).toBeLessThan(all)
  for (const item of await questions.getByRole('listitem').all()) await expect(item).toContainText('Google')
  await company.selectOption({ index: 0 })
  await expect(questions.getByRole('listitem')).toHaveCount(all)
})

import { expect, test, type Page } from '@playwright/test'

const noOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

const isLive = Boolean(process.env.VITE_API_URL)

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': '*',
}

test.describe('Chemical Company Interview Prep', () => {
  test('Field switch works and Computer science still shows existing questions', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#interview-bank')

    // Switch to Computer science
    await page.getByRole('button', { name: 'Computer science' }).click()
    await expect(
      page.getByRole('heading', { name: 'Interview Bank' }),
    ).toBeVisible()
    await expect(page.getByText('How would you detect a cycle in a linked list?')).toBeVisible()

    // Switch back to Chemical
    await page.getByRole('button', { name: 'Chemical' }).click()
    await expect(
      page.getByRole('heading', { name: 'Chemical Company Interview Prep' }),
    ).toBeVisible()
    expect(await noOverflow(page)).toBe(true)
  })

  test('picker lists 15 companies, search filters them, picking one shows details and collapsible section expands', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#interview-bank')

    // Filter by Exxon
    const searchInput = page.getByPlaceholder('Search company...')
    await searchInput.fill('Exxon')
    await expect(page.getByRole('heading', { name: 'ExxonMobil' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Chevron' })).not.toBeVisible()

    // Pick ExxonMobil
    await page.getByRole('heading', { name: 'ExxonMobil' }).click()

    // Verifies What ExxonMobil looks for (always shown)
    await expect(page.getByText('What ExxonMobil looks for')).toBeVisible()

    // Verifies How they select (always shown)
    await expect(page.getByText('How they select')).toBeVisible()

    // Collapsible section (details/summary)
    const techSummary = page.locator('summary', { hasText: 'Technical questions' })
    await expect(techSummary).toBeVisible()
    await techSummary.click()

    // Expanded technical content
    await expect(page.getByText(/Model Answer:/i).first()).toBeVisible()

    // Practice OA link
    const practiceLink = page.getByRole('link', { name: "Practice this company's OA" })
    await expect(practiceLink).toBeVisible()
    await expect(practiceLink).toHaveAttribute('href', '#oa?company=exxonmobil')

    expect(await noOverflow(page)).toBe(true)
  })

  test('own material in demo mode shows sign in message and no file picker', async ({ page }) => {
    test.skip(isLive, 'Demo mode only')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#interview-bank')
    await page.getByRole('heading', { name: 'ExxonMobil' }).click()
    await expect(page.getByText('Sign in to practise from your own material.')).toBeVisible()
    await expect(page.locator('input[type="file"]')).toHaveCount(0)
    expect(await noOverflow(page)).toBe(true)
  })

  test('own material interview practice in live mode', async ({ page }) => {
    test.skip(!isLive, 'Live API only — skipped in demo mode')

    let quizRequestedTopic = ''
    let quizRequestedKinds = ''
    let quizRequestedUploadId = ''
    let practiceAttemptsCalled = false
    let savedTopic = ''

    await page.route(/\/api\/v1\/uploads/, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({ upload_id: 'notes-0123456789abcdef0123456789abcdef' }),
      })
    })

    await page.route(/\/api\/v1\/quizzes/, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      const data = route.request().postDataJSON()
      quizRequestedTopic = data.topic
      quizRequestedKinds = data.kinds
      quizRequestedUploadId = data.upload_id
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-interview-quiz',
          items: [
            {
              type: 'mcq',
              topic: 'Process Safety',
              stem: 'What is a pressure relief valve setting based on?',
              options: ['MAWP', 'Design pressure + 50%', 'Operating pressure', 'None'],
              correct_index: 0,
              explanation: 'PRV is set relative to Maximum Allowable Working Pressure.',
            },
            {
              type: 'mcq',
              topic: 'Distillation',
              stem: 'What happens at total reflux?',
              options: ['Minimum stages', 'Maximum stages', 'Zero stages', 'Infinite feed'],
              correct_index: 0,
              explanation: 'Total reflux yields minimum number of stages.',
            },
            {
              type: 'mcq',
              topic: 'Reaction',
              stem: 'For an exothermic reversible reaction, optimal temperature profile is:',
              options: ['Decreasing along reactor', 'Increasing along reactor', 'Constant', 'None'],
              correct_index: 0,
              explanation: 'High initial rate, then lower temperature to shift equilibrium.',
            },
          ],
        }),
      })
    })

    await page.route(/\/api\/v1\/practice-attempts/, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      practiceAttemptsCalled = true
      const data = route.request().postDataJSON()
      savedTopic = data.topic
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true }),
      })
    })

    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#interview-bank')

    await page.getByRole('heading', { name: 'ExxonMobil' }).click()
    await expect(page.getByText('What ExxonMobil looks for')).toBeVisible()

    // Upload file
    const filePicker = page.locator('input[type="file"]')
    await expect(filePicker).toBeAttached()
    await filePicker.setInputFiles({
      name: 'job_description.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('Job description for Process Engineer'),
    })

    await expect(page.getByText('job_description.pdf')).toBeVisible()
    const makeBtn = page.getByRole('button', { name: 'Make practice questions' })
    await expect(makeBtn).toBeEnabled()
    await makeBtn.click()

    // Assert exam loaded with converted questions
    await expect(
      page.getByRole('heading', { name: 'ExxonMobil interview practice' }),
    ).toBeVisible()
    await expect(page.getByText('Question 1 of 3')).toBeVisible()

    expect(quizRequestedTopic).toBe('Interview: ExxonMobil')
    expect(quizRequestedKinds).toBe('mcq')
    expect(quizRequestedUploadId).toBe('notes-0123456789abcdef0123456789abcdef')

    // NO "Correct" / "Incorrect" text before submit
    await expect(page.getByText('Correct', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Incorrect', { exact: true })).toHaveCount(0)

    // Answer and submit
    await page.locator('input[type="radio"]').first().check()
    await page.getByRole('button', { name: 'Next' }).click()
    await page.locator('input[type="radio"]').first().check()
    await page.getByRole('button', { name: 'Next' }).click()
    await page.locator('input[type="radio"]').first().check()
    await page.getByRole('button', { name: 'Submit' }).click()

    // Verify after submit
    await expect(page.getByText(/Score: \d+ \/ 3 marks/)).toBeVisible()
    expect(practiceAttemptsCalled).toBe(true)
    expect(savedTopic).toBe('Interview: ExxonMobil')
  })
})

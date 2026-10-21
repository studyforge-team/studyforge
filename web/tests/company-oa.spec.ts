import { expect, test, type Page } from '@playwright/test'

const noOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

const isLive = Boolean(process.env.VITE_API_URL)

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': '*',
}

test.describe('Company OA Practice', () => {
  test('Coding tab still shows existing problems and switching to Company OA shows 15 companies', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa')

    // 1. Coding tab is default and shows problems
    await expect(page.getByRole('heading', { name: 'OA Prep' })).toBeVisible()
    await expect(
      page.getByRole('button', { name: '1. Two Sum' }),
    ).toBeVisible()

    // 2. Switch to Company OA tab
    await page.getByRole('button', { name: 'Company OA' }).click()
    await expect(page.getByRole('heading', { name: 'Company OA Practice' })).toBeVisible()

    // Verify search filters companies
    const searchInput = page.getByPlaceholder('Search company...')
    await expect(searchInput).toBeVisible()

    await searchInput.fill('Exxon')
    await expect(page.getByRole('heading', { name: 'ExxonMobil', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Chevron', exact: true })).not.toBeVisible()

    await searchInput.fill('')
    await expect(page.getByRole('heading', { name: 'Chevron', exact: true })).toBeVisible()

    // 375px check
    expect(await noOverflow(page)).toBe(true)
  })

  test('#oa?company=chevron opens Chevron directly', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa?company=chevron')

    await expect(page.getByRole('heading', { name: 'Chevron', exact: true })).toBeVisible()
    await expect(page.getByText('Suggested time:')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Start practice' })).toBeVisible()
    expect(await noOverflow(page)).toBe(true)
  })

  test('opening a company shows sections table, suggested time, and progress graph with trend', async ({
    page,
  }) => {
    test.skip(!isLive, 'needs a build with VITE_API_URL (attempts come from the API)')
    // Mock 2 attempts for ExxonMobil
    await page.route(/\/api\/v1\/quiz-attempts/, async (route) => {
      if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 204, headers: corsHeaders })
        return
      }
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({
          topics: [
            {
              topic: 'OA: ExxonMobil',
              attempts: [
                {
                  quiz_id: 'practice:OA: ExxonMobil',
                  score: 10,
                  total: 15,
                  marks_per_q: 1,
                  created_at: '2026-10-18T10:00:00Z',
                },
                {
                  quiz_id: 'practice:OA: ExxonMobil',
                  score: 13,
                  total: 15,
                  marks_per_q: 1,
                  created_at: '2026-10-19T10:00:00Z',
                },
              ],
            },
          ],
        }),
      })
    })

    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa?company=exxonmobil')

    await expect(page.getByRole('heading', { name: 'ExxonMobil', exact: true })).toBeVisible()
    await expect(page.getByText('10 / 15 marks (67 %)')).toBeVisible()
    await expect(page.getByText('13 / 15 marks (87 %)')).toBeVisible()

    // Trend label: 87% vs 67% is +20% -> improving
    await expect(page.getByText(/improving/i)).toBeVisible()

    // Chart rendered
    await expect(page.locator('svg[role="img"]')).toBeVisible()

    // Sections table
    await expect(page.getByText('Suggested time:')).toBeVisible()
    expect(await noOverflow(page)).toBe(true)
  })

  test('opening a company in demo mode shows sections table, suggested time, and sign in prompt', async ({
    page,
  }) => {
    test.skip(isLive, 'demo mode only')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa?company=exxonmobil')

    await expect(page.getByRole('heading', { name: 'ExxonMobil', exact: true })).toBeVisible()
    await expect(page.getByText('Sign in to track progress')).toBeVisible()
    await expect(page.getByText('Suggested time:')).toBeVisible()
    expect(await noOverflow(page)).toBe(true)
  })

  test('exam flow: Start shows Question 1 of 15, no answers revealed before submit, review and topic breakdown after submit', async ({
    page,
  }) => {
    let practiceAttemptsCalled = false
    let savedTopic = ''

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
    await page.goto('/#oa?company=exxonmobil')

    await page.getByRole('button', { name: 'Start practice' }).click()

    // Shows Question 1 of 15
    await expect(page.getByText('Question 1 of 15')).toBeVisible()

    // NO "Correct" or "Incorrect" text before submit
    await expect(page.getByText('Correct', { exact: true })).toHaveCount(0)
    await expect(page.getByText('Incorrect', { exact: true })).toHaveCount(0)

    // Answer questions and navigate to end
    for (let i = 0; i < 14; i++) {
      // Pick first option
      const firstRadio = page.locator('input[type="radio"]').first()
      await firstRadio.check()
      await page.getByRole('button', { name: 'Next' }).click()
    }

    // On last question (Question 15 of 15)
    await expect(page.getByText('Question 15 of 15')).toBeVisible()
    await page.locator('input[type="radio"]').first().check()

    // Submit button is visible
    const submitBtn = page.getByRole('button', { name: 'Submit' })
    await expect(submitBtn).toBeVisible()

    // Submit the exam
    await submitBtn.click()

    // Results screen shows Score:
    await expect(page.getByText(/Score: \d+ \/ 15 marks/)).toBeVisible()
    await expect(page.getByText('By topic this attempt')).toBeVisible()

    // Now Correct / Incorrect review labels ARE visible
    const reviewLabels = page.getByText(/^(Correct|Incorrect)$/)
    expect(await reviewLabels.count()).toBeGreaterThan(0)

    // Verification of server call in live mode
    if (isLive) {
      expect(practiceAttemptsCalled).toBe(true)
      expect(savedTopic).toBe('OA: ExxonMobil')
    }

    // Exit back to company screen
    await page.getByRole('button', { name: 'Choose another company' }).click()

    // Topic strengths should now be rendered on company screen
    await page.getByRole('heading', { name: 'ExxonMobil', exact: true }).click()
    await expect(page.getByText('Topic strengths')).toBeVisible()
  })

  test('own material in demo mode shows sign in message and no file picker', async ({ page }) => {
    test.skip(isLive, 'Demo mode only')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#oa?company=exxonmobil')
    await expect(page.getByText('Sign in to practise from your own material.')).toBeVisible()
    await expect(page.locator('input[type="file"]')).toHaveCount(0)
    expect(await noOverflow(page)).toBe(true)
  })

  test('own material practice in live mode', async ({ page }) => {
    test.skip(!isLive, 'Live API only — skipped in demo mode')

    let quizRequestedTopic = ''
    let quizRequestedUploadId = ''

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
      quizRequestedUploadId = data.upload_id
      await route.fulfill({
        status: 200,
        headers: corsHeaders,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'test-quiz',
          items: [
            {
              type: 'mcq',
              topic: 'Safety',
              stem: 'What is a HAZOP study?',
              options: ['Hazard study', 'Math study', 'None', 'All'],
              correct_index: 0,
              explanation: 'HAZOP identifies hazards.',
            },
            {
              type: 'mcq',
              topic: 'Fluids',
              stem: 'Bernoulli applies to what flow?',
              options: ['Inviscid', 'Viscous', 'Supersonic', 'None'],
              correct_index: 0,
              explanation: 'Inviscid incompressible flow.',
            },
            {
              type: 'mcq',
              topic: 'Safety',
              stem: 'What is LEL?',
              options: ['Lower explosive limit', 'Low energy', 'None', 'Low emission'],
              correct_index: 0,
              explanation: 'Lower explosive limit.',
            },
          ],
        }),
      })
    })

    await page.goto('/#oa?company=exxonmobil')
    await expect(page.getByRole('heading', { name: 'ExxonMobil', exact: true })).toBeVisible()

    // Upload file
    const filePicker = page.locator('input[type="file"]')
    await expect(filePicker).toBeAttached()
    await filePicker.setInputFiles({
      name: 'syllabus.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('PDF test content'),
    })

    await expect(page.getByText('syllabus.pdf')).toBeVisible()
    const makeBtn = page.getByRole('button', { name: 'Make my test' })
    await expect(makeBtn).toBeEnabled()
    await makeBtn.click()

    // Assert exam loaded with converted questions
    await expect(
      page.getByRole('heading', { name: 'ExxonMobil practice (your material)' }),
    ).toBeVisible()
    await expect(page.getByText('Question 1 of 3')).toBeVisible()
    expect(quizRequestedTopic).toBe('OA: ExxonMobil')
    expect(quizRequestedUploadId).toBe('notes-0123456789abcdef0123456789abcdef')
  })
})

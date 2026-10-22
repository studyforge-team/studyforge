import { expect, test, type Page } from '@playwright/test'

// Demo-mode tests run on the default build. Live tests mock the API with page.route and need a build with
// VITE_API_URL set (same origin as the preview server to avoid CORS, e.g. PW_PORT=4520 VITE_API_URL=http://localhost:4520).
const live = !!process.env.VITE_API_URL
const API = '**/api/v1'

const blankQuiz = {
  id: 'q1', title: 'Heat transfer', topic: 'Heat transfer', marks_per_q: 2, total_marks: 4, suggested_minutes: 6,
  items: [
    { type: 'blank', topic: 'Heat transfer', source: null, tags: [], stem: 'Heat moves by ____ in a solid.', answers: ['conduction'], explanation: 'Conduction needs no bulk motion.' },
    { type: 'blank', topic: 'Heat transfer', source: null, tags: [], stem: 'Fluid motion carries heat by ____.', answers: ['convection', 'advection'], explanation: 'Bulk flow carries energy.' },
  ],
}
const noHScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('the setup form shows, requires a topic, and the live line follows the options', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#quiz')
  await expect(page.getByText('Total: 5 marks · Suggested time: 10 min (keep time yourself)')).toBeVisible()
  await page.getByRole('button', { name: 'Make quiz' }).click()
  await expect(page.getByText('Enter a topic.')).toBeVisible()
  await expect(page.getByText('Loading quiz…')).toHaveCount(0) // nothing was requested
  await page.getByLabel('Mixed').check()
  await page.getByLabel('10', { exact: true }).check()
  await page.getByLabel('4', { exact: true }).check()
  await expect(page.getByText('Total: 40 marks · Suggested time: 30 min (keep time yourself)')).toBeVisible()
  await page.getByRole('button', { name: 'Process control' }).click()
  await expect(page.getByLabel('Topic')).toHaveValue('Process control')
  expect(await noHScroll(page)).toBe(true)
})

test('demo mode: a fill-in-the-blank item is graded ignoring case and spacing', async ({ page }) => {
  test.skip(live, 'demo mode only')
  await page.goto('/#quiz')
  await page.getByLabel('Topic').fill('CSTR')
  await page.getByLabel('Fill in the blanks').check()
  await page.getByRole('button', { name: 'Make quiz' }).click()
  await page.getByLabel('Fill in the blank').fill('  TANK ')
  await page.getByRole('button', { name: 'Check' }).click()
  await expect(page.getByText('Correct.')).toBeVisible()
  await page.getByRole('button', { name: 'Finish' }).click()
  await expect(page.getByText('Results')).toBeVisible()
})

test.describe('live API (mocked with page.route)', () => {
  test.skip(!live, 'needs a build with VITE_API_URL')

  test('options are sent, suggested time and marks result show, blanks ignore case and spaces', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    let body: Record<string, unknown> | undefined
    await page.route(`${API}/quiz-attempts`, (r) => r.fulfill({ status: 401, json: {} }))
    await page.route(`${API}/quizzes`, (r) => { body = r.request().postDataJSON() as Record<string, unknown>; return r.fulfill({ json: blankQuiz }) })
    await page.route(`${API}/quizzes/q1/answers`, (r) => r.fulfill({ json: { recorded: 2 } }))
    await page.goto('/#quiz')
    await page.getByLabel('Topic').fill('  Heat transfer ')
    await page.getByLabel('Fill in the blanks').check()
    await page.getByLabel('10', { exact: true }).check()
    await page.getByLabel('2', { exact: true }).check()
    await page.getByRole('button', { name: 'Make quiz' }).click()
    await expect(page.getByText('Suggested time: 6 min')).toBeVisible()
    expect(body).toEqual({ topic: 'Heat transfer', n_items: 10, kinds: 'blank', marks_per_q: 2 })

    await page.getByLabel('Fill in the blank').fill('  Conduction ')
    await page.getByRole('button', { name: 'Check' }).click()
    await expect(page.getByText('Correct.')).toBeVisible()
    await expect(page.getByText('Conduction needs no bulk motion.')).toBeVisible()
    await page.getByRole('button', { name: 'Next' }).click()
    await page.getByLabel('Fill in the blank').fill('radiation')
    await page.getByRole('button', { name: 'Check' }).click()
    await expect(page.getByText('Incorrect. The answer is: convection or advection')).toBeVisible()
    await page.getByRole('button', { name: 'Finish' }).click()
    await expect(page.getByText('Score: 2 / 4 marks (50 %)')).toBeVisible()
    expect(await noHScroll(page)).toBe(true)
  })

  test('uploaded material is sent as upload_id', async ({ page }) => {
    let body: Record<string, unknown> | undefined
    await page.route(`${API}/quiz-attempts`, (r) => r.fulfill({ status: 401, json: {} }))
    await page.route(`${API}/uploads`, (r) => r.fulfill({ json: { upload_id: 'up1' } }))
    await page.route(`${API}/quizzes`, (r) => { body = r.request().postDataJSON() as Record<string, unknown>; return r.fulfill({ json: blankQuiz }) })
    await page.goto('/#quiz')
    await page.getByLabel('Topic').fill('Heat transfer')
    await page.locator('input[type=file]').setInputFiles({ name: 'notes.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4') })
    await expect(page.getByRole('button', { name: 'Remove material' })).toBeVisible()
    await page.getByRole('button', { name: 'Make quiz' }).click()
    await expect(page.getByText('Suggested time: 6 min')).toBeVisible()
    expect(body).toMatchObject({ topic: 'Heat transfer', upload_id: 'up1' })
  })

  test('skipped items do not count against the student in the total', async ({ page }) => {
    await page.route(`${API}/quiz-attempts`, (r) => r.fulfill({ status: 401, json: {} }))
    await page.route(`${API}/quizzes/q2/**`, (r) => r.fulfill({ json: { recorded: 1 } }))
    const bad = { type: 'numerical', topic: 'Heat transfer', source: null, tags: [], stem: 'Broken key?', key_code: "raise ValueError('bad key')", unit: '-', tolerance_rel: 0.01, worked_solution: 'x' }
    await page.route(`${API}/quizzes`, (r) => r.fulfill({ json: { ...blankQuiz, id: 'q2', marks_per_q: 4, total_marks: 8, suggested_minutes: 6, items: [blankQuiz.items[0], bad] } }))
    await page.goto('/#quiz')
    await page.getByLabel('Topic').fill('Heat transfer')
    await page.getByRole('button', { name: 'Make quiz' }).click()
    await expect(page.getByText(/1 question skipped/)).toBeVisible({ timeout: 120_000 })
    await page.getByLabel('Fill in the blank').fill('conduction')
    await page.getByRole('button', { name: 'Check' }).click()
    await page.getByRole('button', { name: 'Finish' }).click()
    await expect(page.getByText('Score: 4 / 4 marks (100 %)')).toBeVisible()
  })

  test('My progress lists attempts per topic with a chart and a trend', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.route(`${API}/quiz-attempts`, (r) => r.fulfill({ json: { topics: [{ topic: 'Heat transfer', attempts: [
      { quiz_id: 'a', score: 6, total: 10, marks_per_q: 2, created_at: '2026-10-10T09:00:00Z' },
      { quiz_id: 'b', score: 9, total: 10, marks_per_q: 2, created_at: '2026-10-18T09:00:00Z' },
    ] }, ...['OA: Shell', 'OA (my material): Shell', 'Interview: Shell'].map((topic) => ({ topic, attempts: [
      { quiz_id: 'c', score: 1, total: 15, marks_per_q: 1, created_at: '2026-10-19T09:00:00Z' },
    ] }))] } }))
    await page.goto('/#quiz')
    await expect(page.getByRole('heading', { name: 'My progress' })).toBeVisible()
    await expect(page.getByText('12 / 20 marks (60 %) · 10 Oct')).toBeVisible()
    await expect(page.getByText('18 / 20 marks (90 %) · 18 Oct')).toBeVisible()
    await expect(page.getByRole('img', { name: 'Heat transfer: score per attempt' })).toBeVisible()
    await expect(page.getByText('improving')).toBeVisible()
    await expect(page.getByText(/Shell/)).toHaveCount(0) // OA and Interview attempts stay on their own pages
    expect(await noHScroll(page)).toBe(true)
  })
})

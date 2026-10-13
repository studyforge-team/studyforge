import { expect, test, type Page } from '@playwright/test'

// Three chemical engineering papers, oldest first, every question with marks.
// Hand check, reaction engineering: shares 10/25, 10/25, 10/30 by paper; recency weights 1, 2, 3
// -> (0.4*1 + 0.4*2 + 0.333*3) / 6 = 0.367 -> 37 %, and 0.333 < 0.4 - 0.05 -> falling.
const P2019 = `Q1. Derive the design equation of a CSTR and find the volume for 80% conversion. (10 marks)
Q2. Using McCabe-Thiele, find the number of theoretical stages at a reflux ratio of 2. (10 marks)
Q3. A pipe carries water; find the pressure drop using the friction factor. (5 marks)`
const P2021 = `1. Compare PFR and CSTR for a first-order reaction. [10]
2. Find minimum reflux for a benzene-toluene distillation column. [10]
3. Size a heat exchanger with LMTD. [5]`
const P2023 = `Q.1 For the reactor network, find the residence time and conversion (10 marks)
Q.2 A heat exchanger: find the outlet temperatures using LMTD (10 marks)
Q.3 Write a short note on HAZOP (5 marks)
Q.4 Discuss the history of the institute (5 marks)`

async function fill(page: Page, papers: string[]) {
  for (const [i, text] of papers.entries()) await page.locator(`#past-paper-${i + 1}`).fill(text)
}

function row(page: Page, topic: string) {
  return page.getByRole('table', { name: 'Topic frequency' }).getByRole('row').filter({ hasText: topic })
}

test('PYQ predictor ranks chemical topics by marks, recency and trend', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#pyq-predictor')
  await expect(page.getByRole('heading', { name: 'PYQ Predictor', level: 1 })).toBeVisible()
  await fill(page, [P2019, P2021, P2023])
  await page.getByRole('button', { name: 'Predict topics' }).click()

  await expect(page.getByRole('status').filter({ hasText: 'Read 3 papers' })).toContainText('Read 3 papers and 10 questions. Weighted by marks.')
  const rows = page.getByRole('table', { name: 'Topic frequency' }).getByRole('row')
  await expect(rows.nth(1)).toContainText('Reaction engineering') // first data row = most likely
  await expect(row(page, 'Reaction engineering')).toContainText('3 / 3')
  await expect(row(page, 'Reaction engineering')).toContainText('37%')
  await expect(row(page, 'Reaction engineering')).toContainText('falling')
  await expect(row(page, 'Heat transfer')).toContainText('23%')
  await expect(row(page, 'Heat transfer')).toContainText('rising')
  await expect(row(page, 'Safety and environment')).toContainText('new in the latest paper')
  await expect(page.getByText('1 question matched no topic')).toBeVisible()
  await expect(page.getByRole('listitem').filter({ hasText: 'Question 1 · Reaction engineering' })).toBeVisible()
  await expect(page.getByText(/not guaranteed/i)).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('PYQ predictor falls back to question counts when marks are missing', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await fill(page, ['Explain entropy and the second law\nDerive Bernoulli equation', 'Find the LMTD of a heat exchanger\nExplain entropy generation', ''])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Read 2 papers' })).toContainText('Weighted by number of questions')
  await expect(row(page, 'Thermodynamics')).toContainText('2 / 2')
})

test('PYQ predictor needs two papers and chemical engineering content', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await fill(page, ['Q1. Derive the CSTR design equation (10 marks)'])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('alert')).toContainText('at least 2 past papers')
  await expect(page.getByRole('table', { name: 'Topic frequency' })).toHaveCount(0)

  await fill(page, ['Reverse a linked list', 'Binary search on a sorted array'])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('alert')).toContainText('No chemical engineering topics were recognised')
})

test('PYQ predictor: add and remove papers, labels, results cleared on edit, draft kept', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await expect(page.getByText('Past paper 1 (oldest)')).toBeVisible()
  await expect(page.getByText('Past paper 3 (newest)')).toBeVisible()
  for (let i = 0; i < 5; i++) await page.getByRole('button', { name: 'Add another paper' }).click()
  await expect(page.locator('textarea')).toHaveCount(8)
  await expect(page.getByRole('button', { name: 'Add another paper' })).toHaveCount(0)
  for (let i = 0; i < 6; i++) await page.getByRole('button', { name: /^Remove past paper/ }).first().click()
  await expect(page.locator('textarea')).toHaveCount(2)
  await expect(page.getByRole('button', { name: /^Remove past paper/ })).toHaveCount(0)

  await fill(page, [P2019, P2021])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('table', { name: 'Topic frequency' })).toBeVisible()
  await page.locator('#past-paper-2').press('End')
  await page.locator('#past-paper-2').pressSequentially(' edited')
  await expect(page.getByRole('table', { name: 'Topic frequency' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Quiz' }).click()
  await page.getByRole('link', { name: 'PYQ Predictor' }).click()
  await expect(page.locator('#past-paper-1')).toHaveValue(P2019)
  await expect(page.getByRole('link', { name: 'PYQ Predictor' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('link', { name: 'Today' })).not.toHaveAttribute('aria-current', 'page')
})

test('PYQ predictor ignores paper headers and section labels, reads "marks: N", and does not call heat exchanger fluid fluid mechanics', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await fill(page, [
    'Time: 3 hours        Max marks: 100\nAnswer any FIVE questions\nSECTION A\nQ1. Hot fluid enters a heat exchanger; find the LMTD. marks: 10\nQ2. Derive the CSTR design equation. marks: 10',
    'Q1. Size a heat exchanger for a hot fluid stream (10 marks)\nPart II\nQ2. Find the PFR volume for 90% conversion (10 marks)',
  ])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Read 2 papers' })).toContainText('Read 2 papers and 4 questions. Weighted by marks.')
  await expect(row(page, 'Heat transfer')).toContainText('50%')
  await expect(row(page, 'Fluid mechanics')).toHaveCount(0)
  await expect(page.getByText(/matched no topic/)).toHaveCount(0)
})

test('PYQ predictor reads real paper formats: unnumbered headers, sub-part marks, bare Q1 lines, PDF dashes', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await fill(page, [
    // unnumbered paper with a header: the header must not count
    'Max Marks: 100\nDerive the CSTR design equation (10 marks)\nFind the LMTD of a heat exchanger (10 marks)',
    // bare "Q1" lines, sub-parts whose marks add up, a PDF en dash
    'Q1\n(a) Vapour–liquid equilibrium: find the bubble point (5 marks)\n(b) State Raoult’s law (5 marks)\nQ2\nFind the PFR volume for 90% conversion [2+8]',
  ])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Read 2 papers' })).toContainText('Read 2 papers and 4 questions. Weighted by marks.')
  // reaction engineering: 10/20 in paper 1, 10/20 in paper 2 -> 50 %; thermodynamics only in the newest -> new
  await expect(row(page, 'Reaction engineering')).toContainText('50%')
  await expect(row(page, 'Thermodynamics')).toContainText('new in the latest paper')
})

test('PYQ predictor: unit conversion is not reaction engineering; papers without questions do not count', async ({ page }) => {
  await page.goto('/#pyq-predictor')
  await fill(page, ['SECTION A', 'Q1. Do the unit conversion of 5 psi to Pa and find the pump power (5 marks)'])
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(page.getByRole('alert')).toContainText('Only 1 of the pasted papers contain questions')
  await page.locator('#past-paper-1').fill('Q1. Another unit conversion for a pump head (5 marks)')
  await expect(page.getByRole('alert')).toHaveCount(0) // editing clears the old error
  await page.getByRole('button', { name: 'Predict topics' }).click()
  await expect(row(page, 'Fluid mechanics')).toBeVisible()
  await expect(row(page, 'Reaction engineering')).toHaveCount(0)
})

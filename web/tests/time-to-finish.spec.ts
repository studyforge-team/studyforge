import { expect, test } from '@playwright/test'

// Fixed "today" so deadline maths is checkable: Tue 13 Oct 2026, local time.
test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(new Date(2026, 9, 13, 10, 0))
})

test('Time to Finish is reachable from the main navigation', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Time to Finish' }).click()
  await expect(page.getByRole('heading', { name: 'Time to Finish', level: 1 })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Time to Finish' })).toHaveAttribute('aria-current', 'page')
  await expect(page.getByRole('link', { name: 'Today' })).not.toHaveAttribute('aria-current', 'page')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('textbook pages with a revision round and a deadline', async ({ page }) => {
  await page.goto('/#time-to-finish')
  await page.getByLabel(/Textbook or lecture notes/).check()
  await page.getByLabel('Number of pages', { exact: true }).fill('30')
  await page.getByLabel('Rounds through the material').selectOption('2')
  await page.getByLabel('Deadline (optional)').fill('2026-10-20')
  // 30 x 4..8 min x (1 + 0.4) = 168..336 min; 7 days -> 24..48 min a day
  await expect(page.getByTestId('ttf-total')).toHaveText('2 hr 48 min–5 hr 36 min')
  await expect(page.getByTestId('ttf-per-day')).toHaveText('About 24 min–48 min per day for the next 7 days.')
  await expect(page.getByTestId('ttf-basis')).toContainText('typical 4–8 min per page')
  await expect(page.getByTestId('ttf-basis')).toContainText('40 % of the first read')
})

test('own pace overrides the typical rate; problems are counted per problem', async ({ page }) => {
  await page.goto('/#time-to-finish')
  await page.getByLabel('Number of pages', { exact: true }).fill('30')
  await page.getByLabel('Minutes you took').fill('20')
  await page.getByLabel(/you did in that time/).fill('5')
  // 4 min/page +-20 % -> 3.2..4.8 -> 96..144 min
  await expect(page.getByTestId('ttf-total')).toHaveText('1 hr 36 min–2 hr 24 min')
  await expect(page.getByTestId('ttf-basis')).toContainText('your pace')

  await page.getByLabel('Minutes you took').fill('')
  await page.getByLabel(/you did in that time/).fill('')
  await page.getByLabel(/Numerical problems/).check()
  await page.getByLabel('Number of problems', { exact: true }).fill('12')
  // 12 x 10..20 min = 120..240 min
  await expect(page.getByTestId('ttf-total')).toHaveText('2 hr–4 hr')
  await expect(page.getByText('Estimated time for 12 problems')).toBeVisible()
})

test('deadline today, deadline passed, and invalid input', async ({ page }) => {
  await page.goto('/#time-to-finish')
  await page.getByLabel('Deadline (optional)').fill('2026-10-13')
  await expect(page.getByTestId('ttf-per-day')).toContainText('The deadline is today')
  await page.getByLabel('Deadline (optional)').fill('2026-10-01')
  await expect(page.getByTestId('ttf-per-day')).toHaveText('This deadline has already passed.')

  for (const bad of ['0', '-2', '3.5', '1e2', '', '10001']) {
    await page.getByLabel('Number of pages', { exact: true }).fill(bad)
    await expect(page.getByRole('alert')).toContainText('whole number from 1 to 10000')
    await expect(page.getByTestId('ttf-total')).toHaveCount(0)
  }
  await page.getByLabel('Number of pages', { exact: true }).fill('10')
  await page.getByLabel('Minutes you took').fill('20') // pace half-filled: a hint, not an error
  await expect(page.getByTestId('ttf-pace-hint')).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByLabel(/you did in that time/).fill('0') // both filled, one invalid
  await expect(page.getByRole('alert')).toContainText('whole numbers from 1 to 10000 in both boxes')
})

test('a pace does not carry over to another material; tiny totals and a 1-day deadline', async ({ page }) => {
  await page.goto('/#time-to-finish')
  await page.getByLabel('Minutes you took').fill('20')
  await page.getByLabel(/you did in that time/).fill('5')
  await page.getByLabel(/Numerical problems/).check()
  await expect(page.getByLabel('Minutes you took')).toHaveValue('')
  await page.getByLabel('Number of problems', { exact: true }).fill('12')
  await expect(page.getByTestId('ttf-total')).toHaveText('2 hr–4 hr') // typical rate, not the old page pace
  await expect(page.getByTestId('ttf-basis')).not.toContainText('your pace')

  await page.getByLabel(/Slides or short notes/).check()
  await page.getByLabel('Number of pages', { exact: true }).fill('1')
  await page.getByLabel('Minutes you took').fill('1')
  await page.getByLabel(/you did in that time/).fill('10000')
  await page.getByLabel('Deadline (optional)').fill('2026-10-14') // tomorrow
  await expect(page.getByTestId('ttf-total')).toHaveText('<1 min–<1 min')
  await expect(page.getByTestId('ttf-per-day')).toHaveText('About <1 min–<1 min per day for the next 1 day.')

  // 100 pages of slides: 100..300 min over 1 day
  await page.getByLabel('Minutes you took').fill('')
  await page.getByLabel(/you did in that time/).fill('')
  await page.getByLabel('Number of pages', { exact: true }).fill('100')
  await expect(page.getByTestId('ttf-per-day')).toHaveText('About 1 hr 40 min–5 hr per day for the next 1 day.')
})

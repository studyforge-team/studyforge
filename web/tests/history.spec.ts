import { expect, test, type Page } from '@playwright/test'
import { openMenu } from './menu.ts'

// The test build has no VITE_API_URL, so it is demo mode. The live-mode tests need a build with
// VITE_API_URL=https://studyforge-api-s7r7.onrender.com (the CSP allows only that host; the API is mocked with page.route); the demo test needs one without.
const live = !!process.env.VITE_API_URL
const API = 'https://studyforge-api-s7r7.onrender.com/api/v1'
const ago = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString()
const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

const item = (id: string, question: string, h: number, status = 'done') => ({ id, question, status, updated_at: ago(h) })
const FINAL = { type: 'final', answer_md: 'The reactor volume is **42 L**.', numbers: { V: 42 }, figures: [], sources: [], confidence: 'high' }

// cross-origin fetch from the preview server: the mocked API must answer like a CORS-enabled one
const CORS = { 'access-control-allow-origin': '*' }
const ok = (json: unknown, status = 200) => ({ status, json, headers: CORS })

async function mock(page: Page, calls: string[] = []) {
  await page.route(`${API}/solves*`, (route) => {
    const u = new URL(route.request().url())
    calls.push(u.search)
    const q = u.searchParams.get('q')
    if (u.searchParams.get('before')) return route.fulfill(ok({ items: [item('s9', 'Old page two question', 24 * 30)], next: null }))
    if (q) return route.fulfill(ok({ items: [item('s1', 'CSTR volume for 80% conversion', 1)], next: null }))
    route.fulfill(ok({ items: [
      item('s1', 'CSTR volume for 80% conversion', 1),
      item('s2', 'Unfinished heat exchanger question', 30, 'awaiting_result'),
      item('s3', 'Bernoulli pipe flow', 24 * 3),
      item('s4', 'Ancient question', 24 * 20),
    ], next: '2026-01-01T00:00:00+00:00' }))
  })
  await page.route(`${API}/solve/s1`, (route) => route.fulfill(ok({ step: FINAL })))
  await page.route(`${API}/solve/s2`, (route) => route.fulfill(ok({ step: { type: 'run_python', code: '1', timeout_s: 10 } })))
  await page.route(`${API}/solve/gone`, (route) => route.fulfill(ok({ detail: 'solve not found' }, 404)))
}

test.describe('live', () => {
  test.setTimeout(30_000)
  test.skip(!live, 'needs a build with VITE_API_URL')

  test('list groups by day, searches, loads more, at 375px', async ({ page }) => {
    const calls: string[] = []
    await mock(page, calls)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#history')
    await expect(page.getByRole('heading', { name: 'History', level: 1 })).toBeVisible()
    for (const g of ['Today', 'Yesterday', 'Last 7 days', 'Older']) await expect(page.getByRole('region', { name: g })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Today' })).toContainText('CSTR volume')
    await expect(page.getByRole('region', { name: 'Last 7 days' })).toContainText('Bernoulli')
    expect(await noOverflow(page)).toBe(true)
    await page.getByRole('button', { name: 'Load more' }).click()
    await expect(page.getByText('Old page two question')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Load more' })).toHaveCount(0)
    expect(calls.at(-1)).toContain('before=2026-01-01')
    await page.getByLabel('Search your questions').fill('cstr')
    await expect(page.getByText('Bernoulli pipe flow')).toHaveCount(0)
    expect(calls.at(-1)).toBe('?q=cstr')
    const nav = await openMenu(page)
    await expect(nav.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page')
  })

  test('opening an item shows its answer; unfinished and missing say so', async ({ page }) => {
    await mock(page)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/#history')
    await page.getByRole('link', { name: /CSTR volume/ }).click()
    await expect(page).toHaveURL(/#history\/s1$/)
    await expect(page.getByRole('region', { name: 'Answer' })).toContainText('42 L')
    expect(await noOverflow(page)).toBe(true)
    await page.goto('/#history/s2')
    await expect(page.getByText('This solve did not finish.')).toBeVisible()
    await page.goto('/#history/gone')
    await expect(page.getByText('Not found.')).toBeVisible()
    await page.getByRole('link', { name: '← All history' }).click()
    await expect(page.getByRole('heading', { name: 'History', level: 1 })).toBeVisible()
  })

  test('Today recent solves link to their history page', async ({ page }) => {
    await page.route(`${API}/dashboard`, (route) => route.fulfill(ok({ tasks: [], weak_topics: [], reminders: [], recent_solves: [{ id: 's1', question: 'CSTR volume for 80% conversion', status: 'done', created_at: ago(1) }] })))
    await page.goto('/')
    await page.getByRole('link', { name: /CSTR volume/ }).click()
    await expect(page).toHaveURL(/#history\/s1$/)
  })
})

test('demo mode: History needs sign-in', async ({ page }) => {
  test.skip(live, 'demo build only')
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#history')
  await expect(page.getByText('History needs sign-in')).toBeVisible()
  const nav = await openMenu(page)
  await expect(nav.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page')
  expect(await noOverflow(page)).toBe(true)
})

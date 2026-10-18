import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { draftFrom, isHttpUrl, MAX_TEXT, readShare, SHARE_PARAMS, wellFormed } from '../src/lib/share.ts'

// Demo mode (no VITE_API_URL in the test build): notices live in this browser's localStorage.

test('share helpers: fields read, other parameters kept, draft built, links checked', () => {
  const { shared, rest } = readShare('?share_title=CRE&share_text=%20Assignment%203%20due%20Fri%20&share_url=https%3A%2F%2Fx.edu%2Fn&code=abc')
  expect(shared).toEqual({ title: 'CRE', text: 'Assignment 3 due Fri', url: 'https://x.edu/n' })
  expect(rest).toBe('?code=abc') // a sign-in return is never swallowed
  expect(readShare('?code=abc')).toEqual({ shared: null, rest: '?code=abc' })
  expect(readShare('')).toEqual({ shared: null, rest: '' })
  expect(draftFrom({ title: 'T', text: 'see https://x.edu/n', url: 'https://x.edu/n' })).toEqual({ draft: 'see https://x.edu/n', cut: false }) // link not repeated
  expect(draftFrom({ title: 'T', text: 'viva Monday', url: 'https://x.edu/n' }).draft).toBe('viva Monday\nhttps://x.edu/n')
  expect(draftFrom({ title: 'Only a title', text: '', url: '' }).draft).toBe('Only a title')
  expect(draftFrom({ title: '', text: 'x'.repeat(MAX_TEXT + 10), url: '' })).toEqual({ draft: 'x'.repeat(MAX_TEXT), cut: true })
  expect(draftFrom({ title: '', text: 'x'.repeat(MAX_TEXT), url: '' }).cut).toBe(false)
  const emoji = draftFrom({ title: '', text: 'x'.repeat(MAX_TEXT - 1) + '😀', url: '' }).draft // cut through the pair
  expect(emoji).toBe('x'.repeat(MAX_TEXT - 1)) // no lone half left for the server to refuse
  expect(wellFormed('a\uD800b\uDC00c😀')).toBe('abc😀')
  expect(wellFormed('\uDC00\uD800')).toBe('') // reversed halves are not a pair
  for (const ok of ['https://x.edu/n', 'http://a.b/c?d=1', 'HTTPS://X.EDU/n']) expect(isHttpUrl(ok), ok).toBe(true)
  for (const bad of ['javascript:alert(1)', 'data:text/html,x', 'https://', 'https://a.b/c d', 'https://a.b/ x', 'https://a.b/\nx', 'https://a.b/\u200bx', 'https://a.b/\u202ex', 'http:example.com', 'http:/example.com', 'http:\\\\example.com', 'ftp://a.b', ''])
    expect(isHttpUrl(bad), bad).toBe(false)
})

test('manifest: share target matches what the app reads; icons are the declared PNG sizes', async ({ request }) => {
  const r = await request.get('/manifest.webmanifest')
  expect(r.ok()).toBe(true)
  const m = await r.json()
  expect(m.share_target).toEqual({ action: '/', method: 'GET', params: SHARE_PARAMS })
  expect(m).toMatchObject({ name: 'StudyForge', start_url: '/', display: 'standalone' })
  for (const size of [192, 512]) {
    const icon = m.icons.find((i: { sizes: string }) => i.sizes === `${size}x${size}`)
    expect(icon.type).toBe('image/png')
    const png = await (await request.get(icon.src)).body()
    expect(png.subarray(1, 4).toString()).toBe('PNG')
    expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([size, size]) // IHDR width, height
  }
  expect(readFileSync('index.html', 'utf8')).toContain('<link rel="manifest" href="/manifest.webmanifest" />')
})

test('paste a notice, see it after a reload, delete it', async ({ page }) => {
  await page.goto('/#notices')
  await expect(page.getByRole('heading', { name: 'Notices', exact: true })).toBeVisible()
  await expect(page.getByText('No notices yet.')).toBeVisible()
  const save = page.getByRole('button', { name: 'Save notice' })
  await expect(save).toBeDisabled() // nothing to save
  await page.getByLabel('Notice', { exact: true }).fill('  CRE assignment 3 due Friday 5 pm  ')
  await save.click()
  await expect(page.getByRole('status').filter({ hasText: 'Notice saved.' })).toBeVisible()
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('')
  await page.reload()
  const item = page.getByRole('listitem').filter({ hasText: 'CRE assignment 3 due Friday 5 pm' })
  await expect(item).toBeVisible()
  await expect(item).toContainText('Pasted')
  await item.getByRole('button', { name: /^Delete notice: CRE assignment 3/ }).click()
  await expect(page.getByText('No notices yet.')).toBeVisible()
})

test('a shared message opens Notices pre-filled, leaves the address bar, and saves as shared', async ({ page }) => {
  await page.goto('/?share_title=HOD%20office&share_text=Lab%20viva%20moved%20to%20Monday&share_url=https%3A%2F%2Fx.edu%2Fn%2F1')
  await expect(page.getByRole('heading', { name: 'Notices', exact: true })).toBeVisible()
  expect(new URL(page.url()).search).toBe('') // the shared text is not left in the URL or history
  expect(new URL(page.url()).hash).toBe('#notices')
  await expect(page.getByText('Shared to StudyForge from “HOD office”. Check it, then save.')).toBeVisible()
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('Lab viva moved to Monday\nhttps://x.edu/n/1')
  await page.getByRole('button', { name: 'Save notice' }).click()
  const item = page.getByRole('listitem').filter({ hasText: 'Lab viva moved to Monday' })
  await expect(item).toContainText('Shared · HOD office')
  await expect(item.getByRole('link', { name: 'https://x.edu/n/1' })).toHaveAttribute('rel', 'noopener noreferrer nofollow')
})

test('a shared javascript: link is never shown as a link', async ({ page }) => {
  await page.goto('/?share_text=hi&share_url=javascript%3Aalert(1)')
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('hi\njavascript:alert(1)') // kept as plain text to read
  await page.getByRole('button', { name: 'Save notice' }).click()
  const item = page.getByRole('listitem').filter({ hasText: 'hi' })
  await expect(item).toBeVisible()
  await expect(item.getByRole('link')).toHaveCount(0)
})

test('very long shared text is cut to the limit and the page says so', async ({ page }) => {
  await page.goto(`/?share_text=${'x'.repeat(MAX_TEXT + 50)}`)
  await expect(page.getByText(`The shared text was longer than ${MAX_TEXT} characters and was cut.`)).toBeVisible()
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('x'.repeat(MAX_TEXT))
})

test('Notices fits a 375 px phone: no sideways scroll, 44 px targets', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 740 })
  await page.goto('/#notices')
  await page.getByLabel('Notice', { exact: true }).fill('A'.repeat(300)) // one unbroken word must wrap, not widen the page
  await page.getByRole('button', { name: 'Save notice' }).click()
  await expect(page.getByRole('listitem')).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  for (const b of await page.getByRole('button', { name: /Save notice|Delete notice/ }).all())
    expect((await b.boundingBox())!.height).toBeGreaterThanOrEqual(44)
})

test('a shared message survives leaving to sign in, and comes back to Notices', async ({ page }) => {
  await page.goto('/?share_text=Quiz%20moved%20to%20Thursday')
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('Quiz moved to Thursday')
  await page.goto('/?code=returned-from-sign-in') // what the Google sign-in return looks like
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('Quiz moved to Thursday')
  expect(new URL(page.url()).hash).toBe('#notices')
  expect(new URL(page.url()).searchParams.get('code')).toBe('returned-from-sign-in') // left for Supabase
  await page.getByRole('button', { name: 'Discard shared text' }).click()
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('')
  await page.reload()
  await expect(page.getByLabel('Notice', { exact: true })).toHaveValue('') // discarded for good
})

test('broken demo storage is skipped, not rendered', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('studyforge.notices.v1', JSON.stringify([null, {}, { id: 1, text: {} },
    { id: 'ok', text: 'kept', source: 'paste', title: null, url: null, created_at: '2026-10-13T09:00:00Z' }])))
  await page.goto('/#notices')
  await expect(page.getByRole('listitem')).toHaveCount(1)
  await expect(page.getByRole('listitem')).toContainText('kept')
})

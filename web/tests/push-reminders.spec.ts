import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import { expect, test } from '@playwright/test'

// public/sw.js run in a stub worker scope: what it shows, and which page a tap opens.
type Shown = { title: string; opts: { body: string; data: { url: string } } }
function worker() {
  const handlers: Record<string, (e: unknown) => void> = {}
  const shown: Shown[] = []
  const opened: string[] = []
  const navigated: string[] = []
  const windows: { url: string; focus: () => Promise<void>; navigate: (u: string) => Promise<void> }[] = []
  const self = {
    location: { origin: 'https://studyforge.example' },
    addEventListener: (t: string, f: (e: unknown) => void) => { handlers[t] = f },
    skipWaiting: () => {},
    registration: { showNotification: async (title: string, opts: Shown['opts']) => { shown.push({ title, opts }) } },
    clients: { claim: async () => {}, matchAll: async () => windows, openWindow: async (u: string) => { opened.push(u) } },
  }
  vm.runInNewContext(readFileSync('public/sw.js', 'utf8'), { self, URL })
  const fire = async (type: string, e: object) => {
    let p: Promise<unknown> = Promise.resolve()
    handlers[type]({ ...e, waitUntil: (x: Promise<unknown>) => { p = x } })
    await p
  }
  const push = (data: unknown) => fire('push', { data: { json: () => (typeof data === 'string' ? JSON.parse(data) : data) } })
  const click = (url: unknown) => fire('notificationclick', { notification: { close: () => {}, data: { url } } })
  return { shown, opened, navigated, windows, push, click }
}

test('service worker shows the pushed reminder and opens its page', async () => {
  const w = worker()
  await w.push({ title: 'StudyForge reminder', body: 'CRE assignment 3 is due tomorrow.', url: '/#prep/abc' })
  expect(w.shown[0].title).toBe('StudyForge reminder')
  expect(w.shown[0].opts.body).toBe('CRE assignment 3 is due tomorrow.')
  await w.click(w.shown[0].opts.data.url)
  expect(w.opened).toEqual(['https://studyforge.example/#prep/abc'])
})

test('service worker never opens another site, and survives bad pushes', async () => {
  const w = worker()
  for (const url of ['https://evil.example/x', '//evil.example/x', '/\\evil.example/x', 'javascript:alert(1)', 42, null])
    await w.push({ title: 't', body: 'b', url })
  expect(w.shown.map((s) => s.opts.data.url).every((u) => u.startsWith('https://studyforge.example/'))).toBe(true)
  await w.push('null') // valid JSON, not an object: still a notification, never a silent push
  expect(w.shown.at(-1)!.title).toBe('StudyForge')
  await w.push('not json')
  expect(w.shown.at(-1)!.title).toBe('StudyForge') // a default instead of a crash
  await w.push({ title: 'x'.repeat(500), body: 'y'.repeat(5000) })
  expect(w.shown.at(-1)!.title).toHaveLength(100)
  expect(w.shown.at(-1)!.opts.body).toHaveLength(300)
  await w.click('https://evil.example/x') // a tampered notification still opens StudyForge
  expect(w.opened.at(-1)).toBe('https://studyforge.example/')
})

test('a tap focuses an open StudyForge tab instead of opening another', async () => {
  const w = worker()
  w.windows.push({ url: 'https://studyforge.example/#', focus: async () => {}, navigate: async (u) => { w.navigated.push(u) } })
  await w.click('https://studyforge.example/#prep/abc?checkin=7')
  expect(w.navigated).toEqual(['https://studyforge.example/#prep/abc?checkin=7'])
  expect(w.opened).toEqual([])
})

test('Today explains phone reminders in demo mode; the service worker is served', async ({ page, request }) => {
  await page.goto('/')
  const card = page.locator('div', { has: page.getByRole('heading', { name: 'Phone reminders' }) }).last()
  await expect(card).toContainText('Phone reminders work in the live app once you sign in.')
  await expect(card.getByRole('button')).toHaveCount(0)
  const sw = await request.get('/sw.js')
  expect(sw.ok()).toBe(true)
  expect(sw.headers()['content-type']).toContain('javascript')
})

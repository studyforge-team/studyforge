import { expect, test } from '@playwright/test'

type Row = { name: string; pass: boolean; detail: string }
type Win = { __selftest?: Row[] }

test('sandbox self-test passes under real headers', async ({ page, request }) => {
  await page.goto('/?selftest')
  await page.waitForFunction(() => (window as unknown as Win).__selftest, null, { timeout: 180_000 })
  const rows = await page.evaluate(() => (window as unknown as Win).__selftest!)
  console.log(rows.map((r) => `${r.pass ? 'PASS' : 'FAIL'} ${r.name}: ${r.detail}`).join('\n'))
  expect(rows.filter((r) => !r.pass), 'failing cases').toEqual([])

  // The worker script is not referenced by index.html, so read its URL from the page's resource timings.
  const url = await page.evaluate(() => performance.getEntriesByType('resource').map((e) => e.name).find((n) => /\/assets\/worker-.*\.js/.test(n)))
  expect(url, 'worker asset URL').toBeTruthy()
  const csp = (await request.get(url!)).headers()['content-security-policy']
  expect(csp).toBe("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'")
})

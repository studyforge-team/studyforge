// Usage: node scripts/screens.mjs <baseUrl> <outDir>   (not part of the e2e run)
import { chromium } from '@playwright/test'

const [base, out] = process.argv.slice(2)
const Q = 'CSTR first-order reaction, k = 0.2 1/min, tau = 10 min. Find conversion.'
const M = { width: 375, height: 812 }, D = { width: 1280, height: 800 }
const browser = await chromium.launch()

async function shot(name, vp, path, q) {
  const page = await (await browser.newContext({ viewport: vp })).newPage()
  await page.goto(base + path)
  if (q) {
    await page.getByLabel(/your question/i).fill(q)
    await page.getByRole('button', { name: 'Solve' }).click()
    await page.getByRole('region', { name: 'Answer' }).waitFor({ timeout: 120_000 })
    if (q === Q) await page.getByTestId('diagram').locator('svg').waitFor({ timeout: 60_000 })
  } else {
    await page.waitForTimeout(1500)
  }
  await page.waitForTimeout(600)
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true })
  await page.close()
}

await shot('dashboard-375', M, '/')
await shot('dashboard-1280', D, '/')
await shot('solve-answer-375', M, '/#solve', Q)
await shot('solve-answer-1280', D, '/#solve', Q)
await shot('dashboard-empty-375', M, '/?mock=empty')
await shot('solve-lowconf-375', M, '/#solve', 'please fail')
await browser.close()

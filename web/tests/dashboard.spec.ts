import { expect, test, type Page } from '@playwright/test'

const noOverflow = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

for (const vp of [{ width: 375, height: 812 }, { width: 1280, height: 800 }]) {
  test(`dashboard at ${vp.width}px`, async ({ page }) => {
    await page.setViewportSize(vp)
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'What do I do today?' })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Today' })).toContainText('CRE assignment 3')
    const inbox = page.getByRole('region', { name: 'Reminders inbox' })
    const item = inbox.getByRole('listitem').filter({ hasText: 'open your prep pack' })
    await expect(item).toContainText('New')
    await expect(item).toContainText('Telegram')
    await expect(inbox).toContainText('Scheduled')
    expect(await noOverflow(page)).toBe(true)
    await page.getByRole('button', { name: 'Ask a question' }).click()
    await expect(page.getByLabel('Your question')).toBeVisible()
    await page.getByRole('link', { name: '← Today' }).click()
    await expect(page.getByRole('heading', { name: 'What do I do today?' })).toBeVisible()
  })
}

test('empty dashboard shows empty states', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/?mock=empty')
  await expect(page.getByText('Nothing due in the next 48 hours.')).toBeVisible()
  for (const t of ['No open deadlines.', 'No weak topics yet', 'No solves yet', 'No reminders yet.']) await expect(page.getByText(t)).toBeVisible()
})

test('fired reminders are no longer New after a reload', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/')
  await expect(page.getByText('New', { exact: true }).first()).toBeVisible()
  // inbox is below the fold: never scrolled, so it is never seen and "New" must survive a reload
  await page.waitForTimeout(4000)
  await page.reload()
  await expect(page.getByText('open your prep pack')).toBeVisible()
  await expect(page.getByText('New', { exact: true }).first()).toBeVisible()
  // scroll the inbox into view and keep it on screen for ≥1 s, then "New" must clear
  await page.getByRole('region', { name: /reminders/i }).scrollIntoViewIfNeeded()
  await page.waitForTimeout(2000)
  await page.reload()
  await expect(page.getByText('open your prep pack')).toBeVisible()
  await expect(page.getByText('New', { exact: true })).toHaveCount(0)
})

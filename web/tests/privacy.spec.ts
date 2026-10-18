import { expect, test } from '@playwright/test'

for (const vp of [{ width: 375, height: 812 }, { width: 1280, height: 800 }]) {
  test(`privacy panel at ${vp.width}px (demo)`, async ({ page }) => {
    await page.setViewportSize(vp)
    await page.goto('/#privacy')
    await expect(page.getByRole('heading', { name: 'Your data' })).toBeVisible()
    await expect(page.getByText('Sign in to download or delete your data.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Download my data' })).toBeDisabled()
    // demo: signed out, so the DELETE box is locked too; typing is impossible and the button stays off
    await expect(page.getByLabel('Type DELETE to confirm')).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Delete my account' })).toBeDisabled()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    for (const n of ['Download my data', 'Delete my account']) {
      expect((await page.getByRole('button', { name: n }).boundingBox())!.height).toBeGreaterThanOrEqual(44)
    }
  })
}

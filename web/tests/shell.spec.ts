import { expect, test } from '@playwright/test'
import { openMenu } from './menu.ts'

for (const width of [320, 375]) {
  test(`top bar has no nav links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    await page.goto('/')
    await expect(page.locator('header a')).toHaveCount(0)
    await expect(page.locator('header')).toContainText('Today')
    // keepMounted: closed drawer keeps its links in the DOM
    await expect(page.getByRole('link', { name: 'Quiz', includeHidden: true })).toBeAttached()
    await expect(page.getByRole('link', { name: 'Quiz' })).toHaveCount(0)
  })
}

test('menu opens and closes by button, Esc and scrim; a link navigates and closes', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 })
  await page.goto('/')
  const btn = page.getByRole('button', { name: 'Menu', exact: true })
  const nav = page.getByRole('navigation', { name: 'Main' })
  await btn.click()
  await expect(nav).toBeVisible()
  await page.getByRole('button', { name: 'Close menu' }).click()
  await expect(nav).toBeHidden()
  await expect(btn).toBeFocused() // focus returns to the menu button
  await btn.click()
  await page.keyboard.press('Escape')
  await expect(nav).toBeHidden()
  await btn.click()
  await page.mouse.click(360, 400) // scrim, right of the 72*4=288px drawer
  await expect(nav).toBeHidden()
  await (await openMenu(page)).getByRole('link', { name: 'Quiz' }).click()
  await expect(nav).toBeHidden()
  await expect(page).toHaveURL(/#quiz$/)
  await expect(page.locator('header')).toContainText('Quiz')
})

test('settings page renders and is titled', async ({ page }) => {
  await page.goto('/#settings')
  await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible()
  await expect(page.locator('header')).toContainText('Settings')
  await expect(page.getByRole('link', { name: 'Privacy policy' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0) // signed out
})

test('theme: Dark persists across reload, Light removes it, System follows the OS', async ({ page }) => {
  const dark = () => page.evaluate(() => document.documentElement.classList.contains('dark'))
  await page.emulateMedia({ colorScheme: 'light' })
  await page.goto('/#settings')
  await page.getByLabel('Dark').check()
  expect(await dark()).toBe(true)
  await page.reload()
  expect(await dark()).toBe(true)
  await expect(page.getByLabel('Dark')).toBeChecked()
  await page.getByLabel('Light').check()
  expect(await dark()).toBe(false)
  await page.reload()
  expect(await dark()).toBe(false)
  await page.getByLabel('System').check()
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect.poll(dark).toBe(true)
  await page.emulateMedia({ colorScheme: 'light' })
  await expect.poll(dark).toBe(false)
})

test('theme-init.js loads under the CSP and paints dark before the app', async ({ page, request }) => {
  const res = await request.get('/')
  expect(res.headers()['content-security-policy']).toContain("script-src 'self'")
  expect(await res.text()).toContain('src="/theme-init.js"')
  await page.addInitScript(() => localStorage.setItem('sf-theme', 'dark'))
  const errors: string[] = []
  page.on('console', (m) => m.text().includes('Content Security Policy') && errors.push(m.text()))
  await page.goto('/')
  expect(await page.evaluate(() => document.querySelector('meta[name=theme-color]')!.getAttribute('content'))).toBe('#171512')
  expect(errors).toEqual([])
  expect((await request.get('/theme-init.js')).status()).toBe(200)
})

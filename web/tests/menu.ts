import { expect, type Page } from '@playwright/test'

// The main nav lives in a drawer at every width; open it (no-op if already open) and return the nav.
// aria-expanded, not nav visibility: a drawer that is still animating closed is "visible" but closed.
export async function openMenu(page: Page) {
  const btn = page.getByRole('button', { name: 'Menu', exact: true })
  if ((await btn.getAttribute('aria-expanded')) !== 'true') await btn.click()
  const nav = page.getByRole('navigation', { name: 'Main' })
  await expect(nav).toBeVisible()
  return nav
}

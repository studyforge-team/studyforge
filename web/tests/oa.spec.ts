import { expect, test } from '@playwright/test'

const TWO_SUM = `def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
result = None`

const TWO_SUM_REVERSED = `def two_sum(nums, target):
    for j in range(len(nums)):
        for i in range(j):
            if nums[i] + nums[j] == target:
                return (j, i)
result = None`

async function runTests(page: import('@playwright/test').Page, code: string) {
  await page.getByLabel('Your python solution').fill(code)
  await page.getByRole('button', { name: 'Run sample tests' }).click()
  const status = page.locator('main [role=status]')
  await expect(status).toHaveText(/passed|error/i, { timeout: 120_000 })
  return status.innerText()
}

test('OA prep: correct, reordered, wrong and broken solutions', async ({ page }) => {
  await page.goto('/#oa')
  await expect(page.getByRole('heading', { name: 'OA Prep', level: 1 })).toBeVisible()
  expect(await runTests(page, TWO_SUM)).toBe('3/3 sample tests passed')
  expect(await runTests(page, TWO_SUM_REVERSED)).toBe('3/3 sample tests passed')
  await page.getByRole('group', { name: 'Choose a problem' }).getByRole('button', { name: /Valid Palindrome/ }).click()
  expect(await runTests(page, 'def is_palindrome(s):\n    return False\nresult = None')).toBe('1/3 sample tests passed')
  expect(await runTests(page, 'def is_palindrome(s)\n    return True')).toBe("Execution error: SyntaxError: expected ':'")
})

for (const width of [320, 360, 375]) {
  test(`no sideways scroll with all nav links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 })
    for (const hash of ['#', '#oa', '#interview-bank', '#chemlab']) {
      await page.goto('/' + hash)
      await expect(page.getByRole('link', { name: 'OA Prep' })).toBeAttached()
      await expect(page.getByRole('link', { name: 'Interview Bank' })).toBeAttached()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), hash).toBe(true)
    }
  })
}

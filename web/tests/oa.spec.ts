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
    for (const hash of ['#', '#oa', '#interview-bank', '#pyq-predictor', '#time-to-finish', '#chemlab']) {
      await page.goto('/' + hash)
      await expect(page.getByRole('link', { name: 'OA Prep' })).toBeAttached()
      await expect(page.getByRole('link', { name: 'Interview Bank' })).toBeAttached()
      await expect(page.getByRole('link', { name: 'PYQ Predictor' })).toBeAttached()
      await expect(page.getByRole('link', { name: 'Time to Finish' })).toBeAttached()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), hash).toBe(true)
    }
  })
}

async function pick(page: import('@playwright/test').Page, name: RegExp) {
  await page.getByRole('group', { name: 'Choose a problem' }).getByRole('button', { name }).click()
}

test('OA prep: wrong answers fail, None compares, errors keep the other results', async ({ page }) => {
  await page.goto('/#oa')
  expect(await runTests(page, 'def two_sum(nums, target):\n    return [0, 0]')).toBe('0/3 sample tests passed')
  await pick(page, /First Non-Repeating/)
  const firstUnique = `from collections import Counter
def first_unique(s):
    c = Counter(s)
    return next((ch for ch in s if c[ch] == 1), None)`
  expect(await runTests(page, firstUnique)).toBe('3/3 sample tests passed')
  // crashes only on "aabb" (test 2): the other two results still count
  const crashOnAabb = `def first_unique(s):
    if s == "aabb":
        raise ValueError("boom")
    return {"swiss": "w", "leetcode": "l"}[s]`
  expect(await runTests(page, crashOnAabb)).toBe('2/3 sample tests passed. Error in test 2: ValueError: boom')
})

test('OA prep: an infinite loop is explained', async ({ page }) => {
  await page.goto('/#oa')
  await pick(page, /Valid Palindrome/)
  const out = await runTests(page, 'def is_palindrome(s):\n    while True:\n        pass')
  expect(out).toContain('took longer than 10 s')
})

test('OA prep: drafts and results survive leaving the page', async ({ page }) => {
  await page.goto('/#oa')
  expect(await runTests(page, TWO_SUM)).toBe('3/3 sample tests passed')
  await page.getByRole('link', { name: 'Quiz' }).click()
  await page.getByRole('link', { name: 'OA Prep' }).click()
  await expect(page.getByLabel('Your python solution')).toHaveValue(TWO_SUM)
  await expect(page.locator('main [role=status]')).toHaveText('3/3 sample tests passed')
  await expect(page.getByRole('button', { name: /Two Sum/ })).toHaveAttribute('aria-pressed', 'true')
})

test('OA prep: switching problem while tests run does not leave a stuck state', async ({ page }) => {
  await page.goto('/#oa')
  await page.getByLabel('Your python solution').fill('import time\ndef two_sum(nums, target):\n    time.sleep(1)\n    return [0, 1]')
  await page.getByRole('button', { name: 'Run sample tests' }).click()
  await pick(page, /Valid Palindrome/)
  await expect(page.locator('main [role=status]')).toHaveText('Another problem is still running its tests…')
  await pick(page, /Two Sum/)
  await expect(page.locator('main [role=status]')).toHaveText(/sample tests passed/, { timeout: 120_000 })
  await expect(page.getByRole('button', { name: 'Run sample tests' })).toBeEnabled()
})

test('OA prep: the starter example call and a student result variable are both handled', async ({ page }) => {
  await page.goto('/#oa')
  // the starter-style last line is skipped: here it would crash every test if it ran
  const crashingExample = `def two_sum(nums, target):
    if len(nums) < 2:
        raise ValueError("needs two numbers")
    seen = {}
    for i, n in enumerate(nums):
        if target - n in seen:
            return [seen[target - n], i]
        seen[n] = i
result = two_sum([1], 5)`
  expect(await runTests(page, crashingExample)).toBe('3/3 sample tests passed')
  // a module-level variable named result must not be deleted
  const usesResult = `result = []
def two_sum(nums, target):
    result.clear()
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                result.extend([i, j])
                return list(result)`
  expect(await runTests(page, usesResult)).toBe('3/3 sample tests passed')
})

test('OA prep: damaged saved data is ignored and editing clears an old result', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('studyforge.oa.v1', '{"codes":{"two-sum":5},"status":{"two-sum":7}}'))
  await page.goto('/#oa')
  await expect(page.getByLabel('Your python solution')).toHaveValue(/def two_sum/)
  await expect(page.locator('main [role=status]')).toHaveText('No submission yet.')
  expect(await runTests(page, TWO_SUM)).toBe('3/3 sample tests passed')
  await page.getByLabel('Your python solution').press('End')
  await page.getByLabel('Your python solution').pressSequentially('\n# edited')
  await expect(page.locator('main [role=status]')).toHaveText('No submission yet.')
})

test('OA prep: editing during a run does not show a result for the old code', async ({ page }) => {
  await page.goto('/#oa')
  await page.getByLabel('Your python solution').fill('import time\ndef two_sum(nums, target):\n    time.sleep(1)\n    return [0, 1]')
  await page.getByRole('button', { name: 'Run sample tests' }).click()
  await page.getByLabel('Your python solution').press('End')
  await page.getByLabel('Your python solution').pressSequentially('\n# edited')
  await expect(page.locator('main [role=status]')).toHaveText('Code changed during the run. Run the tests again.', { timeout: 120_000 })
})

import { expect, test } from '@playwright/test'
import { openMenu } from './menu.js'

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    class Recognition {
      onstart?: () => void
      onend?: () => void
      onerror?: (event: { error: string }) => void
      onresult?: (event: { results: { 0: { transcript: string }; isFinal: boolean }[] }) => void
      start() { Object.assign(window, { testRecognition: this }); this.onstart?.() }
      stop() { this.onend?.() }
      abort() { Object.assign(window, { voiceAborted: true }); this.onend?.() }
    }
    Object.assign(window, { SpeechRecognition: Recognition })
  })
})

test('dictation appends once, preserves draft, and never auto-sends', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/#solve')
  await page.getByLabel('Your question', { exact: true }).fill('Find conversion.')
  await page.getByRole('button', { name: 'Start voice input' }).click()
  await expect(page.getByRole('button', { name: 'Solve', exact: true })).toBeDisabled()
  await page.evaluate(() => {
    const recognition = (window as unknown as { testRecognition: { onresult: (e: unknown) => void } }).testRecognition
    recognition.onresult({ results: [{ 0: { transcript: 'For a reactor' }, isFinal: false }] })
    recognition.onresult({ results: [{ 0: { transcript: 'For a CSTR.' }, isFinal: true }] })
    recognition.onresult({ results: [{ 0: { transcript: 'For a CSTR.' }, isFinal: true }] })
  })
  await page.getByRole('button', { name: 'Stop voice input' }).click()
  await expect(page.getByLabel('Your question', { exact: true })).toHaveValue('Find conversion. For a CSTR.')
  await expect(page.getByLabel('Your question', { exact: true })).toBeEditable()
  await expect(page.getByRole('region', { name: 'Answer', exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('cancel discards dictation and navigation stops the microphone', async ({ page }) => {
  await page.goto('/#solve')
  await page.getByLabel('Your question', { exact: true }).fill('Original draft')
  await page.getByRole('button', { name: 'Start voice input' }).click()
  await page.evaluate(() => {
    const recognition = (window as unknown as { testRecognition: { onresult: (e: unknown) => void } }).testRecognition
    recognition.onresult({ results: [{ 0: { transcript: 'Discard this' }, isFinal: true }] })
  })
  await page.getByRole('button', { name: 'Cancel voice input' }).click()
  await expect(page.getByLabel('Your question', { exact: true })).toHaveValue('Original draft')
  await page.getByRole('button', { name: 'Start voice input' }).click()
  await page.evaluate(() => Object.assign(window, { voiceAborted: false }))
  await (await openMenu(page)).getByRole('link', { name: 'Today', exact: true }).click()
  await expect.poll(() => page.evaluate(() => (window as unknown as { voiceAborted: boolean }).voiceAborted)).toBe(true)
})

test('permission denial allows retry and typing', async ({ page }) => {
  await page.goto('/#solve')
  await page.getByRole('button', { name: 'Start voice input' }).click()
  await page.evaluate(() => {
    const recognition = (window as unknown as { testRecognition: { onerror: (e: unknown) => void; onend: () => void } }).testRecognition
    recognition.onerror({ error: 'not-allowed' })
    recognition.onend?.()
  })
  await expect(page.getByRole('alert')).toContainText('Microphone access was denied')
  await expect(page.getByRole('button', { name: 'Start voice input' })).toBeEnabled()
  await expect(page.getByLabel('Your question', { exact: true })).toBeEditable()
})

test('unsupported browsers retain typing with an explanation', async ({ page }) => {
  await page.addInitScript(() => Object.assign(window, { SpeechRecognition: undefined, webkitSpeechRecognition: undefined }))
  await page.goto('/#solve')
  await expect(page.getByRole('button', { name: 'Start voice input' })).toBeDisabled()
  await expect(page.getByText('Voice input is not supported in this browser. You can still type your question.')).toBeVisible()
  await expect(page.getByLabel('Your question', { exact: true })).toBeEditable()
})

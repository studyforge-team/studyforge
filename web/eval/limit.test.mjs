import { test } from 'node:test'
import assert from 'node:assert/strict'
import { limitReached } from './limit.mjs'

test('detects a cap in an immediate final before the page renders it', () => {
  assert.equal(limitReached('', { answer_md: "Today's AI limit is reached, so I can't solve a new question right now." }), true)
})
test('detects the saved-answer cap banner too', () => {
  assert.equal(limitReached('', { answer_md: "Today's AI limit is reached, so here is a saved answer to the same question:\nAnswer: 107.1 kg/h" }), true)
})
test('detects a page-only cap while the request is pending', () => {
  assert.equal(limitReached('Today’s AI limit is reached. Try again tomorrow.'), true)
})
test('normal answers and missing finals do not stop the run', () => {
  assert.equal(limitReached(), false)
  assert.equal(limitReached('Solving…', { answer_md: 'V = 0.1943 m³' }), false)
})

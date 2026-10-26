import { test } from 'node:test'
import assert from 'node:assert/strict'
import { splitQuestions } from '../src/lib/splitQuestions.ts'

const sheet = `Tutorial 5
CH-202
Question 1. Estimate dH for CO2 from 70 C and 150 bar to 20 C and 15 bar.
Question 2. Estimate V, H^R and S^R for an equimolar mixture.
Question 3. Calculate H and S of saturated isobutane vapor at 360 K:
P bar 340 K 350 K
0.10 0.99700 0.99719
Cp^ig/R = 1.7765 + 33.037 x 10^-3 T`

test('a numbered sheet splits into its questions, data stays with its question', () => {
  const parts = splitQuestions(sheet)
  assert.deepEqual(parts.map((p) => p.label), ['Question 1', 'Question 2', 'Question 3'])
  assert.ok(parts[0].text.startsWith('Question 1.') && !parts[0].text.includes('Tutorial'))
  assert.ok(parts[2].text.includes('0.99719') && parts[2].text.includes('Cp^ig/R'))
})
test('Q1) / Problem 2: headings work too', () => {
  assert.equal(splitQuestions('Q1) Find X.\nProblem 2: Find Y.').length, 2)
})
test('one question stays whole, even with (a) (b) parts or numbered steps', () => {
  const one = 'Find the volume. (a) at 300 K (b) at 400 K\n1. use PV = nRT\n2. compare'
  assert.deepEqual(splitQuestions(one), [{ label: '', text: one }])
})
test('a word like "quality" or a value like Q = 5 kW is not a heading', () => {
  assert.equal(splitQuestions('quality 2 is 0.9\nQ = 5 kW is removed\nQuestion 1. only one').length, 1)
})

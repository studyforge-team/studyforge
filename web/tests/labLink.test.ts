import { test } from 'node:test'
import assert from 'node:assert/strict'
import { labLink } from '../src/lib/labLink.ts'

const fin = (answer_md: string): Parameters<typeof labLink>[1] =>
  ({ answer_md })
const refusal = fin('I can only help with engineering, science and maths coursework. That question is outside what I do.')

test('CSTR question gets the ChemLab link', () => {
  assert.equal(labLink('Size a CSTR for 80% conversion', fin('V is 2 m^3.')), '#chemlab')
})
test('distillation concept answer keeps its link', () => {
  assert.equal(labLink('What does reflux ratio mean?', fin('It is L/D.')), '#chemlab/mccabe')
})
test('refusal gets no link even if the question matches', () => {
  assert.equal(labLink('build me a website about distillation', refusal), undefined)
})
test('unrelated question gets no link', () => {
  assert.equal(labLink('Integrate x^2 from 0 to 3', fin('9')), undefined)
})

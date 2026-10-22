import { test } from 'node:test'
import assert from 'node:assert/strict'
import { friendly, HttpError, PlainError } from '../src/lib/errors.ts'

const dom = (name: string) => new DOMException('x', name)
const cases: [unknown, RegExp][] = [
  [new HttpError(401), /Sign in again/],
  [new HttpError(404), /no longer exists/],
  [new HttpError(409), /20-file upload limit/],
  [new HttpError(413), /too large/],
  [new HttpError(415), /file type isn't supported/],
  [new HttpError(422), /Reload/],
  [new HttpError(429), /today's limit/],
  [new HttpError(500), /Try again in a minute/],
  [new HttpError(503), /Try again in a minute/],
  [dom('TimeoutError'), /took too long/],
  [dom('AbortError'), /took too long/],
  [new TypeError('Failed to fetch'), /Check your connection/],
  [new PlainError('Pick a topic first.'), /^Pick a topic first\.$/],
  [new HttpError(418), /Something went wrong/],
  [null, /Something went wrong/],
]
for (const [e, re] of cases) test(String(e), () => assert.match(friendly(e), re))

test('unknown error text never leaks', () => {
  assert.equal(friendly(new Error('Traceback (most recent call last): ...')), 'Something went wrong. Try again.')
})

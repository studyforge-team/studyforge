// Live eval of the deployed StudyForge solver (SV0). Not under web/tests: Playwright and CI never run it.
// Usage: node web/eval/eval_live.mjs [--only id1,id2] [--out file.json] [--questions file.json]   (site: EVAL_SITE or the default below)
import { chromium } from '@playwright/test'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const arg = (n) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : undefined }
const SITE = process.env.EVAL_SITE || 'https://studyforge-ten-alpha.vercel.app'
const API = 'https://studyforge-api-s7r7.onrender.com'
const OUT = resolve(arg('--out') || resolve(here, 'out/last_run.json'))
const only = arg('--only')?.split(',')
const all = JSON.parse(readFileSync(resolve(arg('--questions') || resolve(here, '../../docs/eval/sv_questions.json')), 'utf8'))
const qs = only ? all.filter((q) => only.includes(q.id)) : all
if (!qs.length) throw new Error('no questions selected')

const LIMIT = /Today.s AI limit is reached/i
// ponytail: small regex list; widen if a real refusal wording slips through
const REFUSAL = [
  /(can|could) only (help|answer|assist|support)/i, /only (able to )?(help|assist)/i,
  /engineering (and|or|&) science/i, /(science|engineering) (and|or) engineering/i,
  /coursework/i, /(outside|beyond) (of )?(my|the|this) (scope|remit)/i, /can.t help with that/i,
]
const isRefusal = (f) => !Object.keys(f.numbers || {}).length && REFUSAL.some((r) => r.test(f.answer_md || ''))
// ponytail: magnitudes only (work/heat sign conventions differ); a pure sign error would pass
const near = (v, want, tol) => Number.isFinite(v) && Math.abs(Math.abs(v) - Math.abs(want)) <= tol * Math.abs(want)
// a correct value in a 10^3-prefixed unit (L vs m^3, J vs kJ) counts; the answer's unit is in its key name
const hasNum = (nums, want, tol) => Object.values(nums || {}).some((v) => [1, 1e3, 1e-3, 1e6, 1e-6].some((s) => near(Number(v) * s, want, tol)))

// judge the final answer only: if numbers has "answer..." keys, only those count (not check/helper values)
const hasAnswer = (nums, want, tol) => {
  const a = Object.fromEntries(Object.entries(nums || {}).filter(([k]) => /^answer/.test(k)))
  return hasNum(Object.keys(a).length ? a : nums, want, tol)
}

function grade(q, f) {
  const e = q.expect, md = f.answer_md || '', refused = isRefusal(f)
  if (e.refuse === true) return refused ? [true, 'refused'] : [false, 'not refused']
  if (refused) return [false, 'refused an on-topic question']
  const why = []
  if ('value' in e && !hasAnswer(f.numbers, e.value, e.rel_tol)) why.push(`no number within ${e.rel_tol * 100}% of ${e.value}`)
  if (e.must_assume && !/assum/i.test(md)) why.push('no assumption stated')
  if (e.also) {
    if (typeof e.also === 'string' ? !md.toLowerCase().includes(e.also.toLowerCase()) : !hasNum(f.numbers, e.also.value, e.rel_tol)) why.push(`missing second part ${JSON.stringify(e.also)}`)
  }
  if (e.keywords) {
    const hits = e.keywords.filter((k) => md.toLowerCase().includes(k.toLowerCase()))
    if (hits.length < (e.min_hits || 1)) why.push(`keywords ${hits.length}/${e.min_hits || 1}`)
  }
  return why.length ? [false, why.join('; ')] : [true, 'ok']
}

// the "final" object, wherever the response carries it
const finalOf = (b) => b?.final ?? (b?.step?.type === 'final' ? b.step : b?.type === 'final' ? b : null)

// cold start: poll /health until 200 (up to ~2 min)
for (let i = 0; i < 40; i++) {
  try { if ((await fetch(`${API}/health`)).status === 200) break } catch {}
  if (i === 39) throw new Error('API never became healthy')
  await new Promise((r) => setTimeout(r, 3000))
}

const browser = await chromium.launch()
const page = await (await browser.newContext()).newPage()
let cur = null // { finals: [], bodies: [] } for the question in flight
page.on('response', async (r) => {
  if (!cur || !r.url().includes('/api/v1/solve')) return
  try {
    const b = await r.json()
    cur.bodies.push(b)
    const f = finalOf(b)
    if (f) cur.final = { ...f, kind: b.kind ?? b.step?.kind ?? f.kind }
  } catch {}
})

await page.goto(`${SITE}/#solve`)
const demo = page.getByRole('button', { name: 'Try demo' })
if (await demo.isVisible({ timeout: 8000 }).catch(() => false)) { await demo.click(); await page.waitForTimeout(2000) }

const rows = []
let aborted = null
for (const q of qs) {
  await page.goto(`${SITE}/#solve`)
  await page.reload()
  cur = { bodies: [], final: null }
  const t0 = Date.now()
  try {
    await page.locator('main textarea').first().fill(q.question)
    await page.getByRole('button', { name: 'Solve', exact: true }).click()
  } catch (err) { cur.err = String(err).split('\n')[0] }
  while (!cur.final && !cur.err && Date.now() - t0 < 150_000) {
    if (LIMIT.test(await page.locator('body').innerText().catch(() => ''))) { aborted = q.id; break }
    await page.waitForTimeout(500)
  }
  if (aborted) break
  const f = cur.final
  const seconds = +((Date.now() - t0) / 1000).toFixed(1)
  const [pass, reason] = f ? grade(q, f) : [false, cur.err || 'timeout / no final']
  const row = {
    id: q.id, category: q.category, seconds, confidence: f?.confidence ?? null, kind: f?.kind ?? null,
    numbers: f?.numbers ?? null, answer_md: f?.answer_md ?? null, pass, reason,
    wrong_high: !pass && q.expect.refuse !== true && f?.confidence === 'high',
  }
  rows.push(row)
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${q.id.padEnd(28)} ${String(row.confidence).padEnd(7)} ${String(seconds).padStart(6)}s  ${reason}`)
}
await browser.close()

const secs = rows.map((r) => r.seconds).sort((a, b) => a - b)
const mid = secs.length ? (secs[(secs.length - 1) >> 1] + secs[secs.length >> 1]) / 2 : 0
const plain = rows.filter((r) => r.category === 'plain_calc')
const totals = {
  run: rows.length, pass: rows.filter((r) => r.pass).length, wrong_high: rows.filter((r) => r.wrong_high).length,
  plain_calc: plain.length, plain_calc_high: plain.filter((r) => r.confidence === 'high').length,
  mean_s: +(secs.reduce((a, b) => a + b, 0) / (secs.length || 1)).toFixed(1), median_s: +mid.toFixed(1), aborted,
}
console.log('\nTOTALS', JSON.stringify(totals))
mkdirSync(dirname(OUT), { recursive: true })
writeFileSync(OUT, JSON.stringify({ site: SITE, at: new Date().toISOString(), totals, rows }, null, 1))
if (aborted) { console.error(`ABORTED at ${aborted}: daily AI limit reached, later answers would be cached`); process.exit(2) }

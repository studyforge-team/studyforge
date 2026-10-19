import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getQuiz, reportItem, saveAnswers } from '@/api/client'
import type { NumericalItem, Quiz as QuizData, QuizItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { friendly, PlainError } from '@/lib/errors'
import { checkKey, fillSolution, fmt4 } from '@/quiz/key'
import { run, warm } from '@/sandbox/client'

const TOPIC = 'Reactor basics' // ponytail: no topic picker yet; live mode asks the backend for this fixed topic
const field = 'rounded-lg border border-input bg-background p-3 text-base focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60'
const row = 'flex min-h-11 items-center gap-3 rounded-lg border p-3 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:checked]:border-primary'
type Prepared = { item: QuizItem; idx: number; key?: { value: number; solution: string } } // idx: position in the quiz as served
type Done = { topic: string; score: number; answer: string }

function Question({ p, n, total, onNext, extra }: { p: Prepared; n: number; total: number; onNext: (d: Done) => void; extra?: ReactNode }) {
  const { item } = p
  const [pick, setPick] = useState<number>()
  const [text, setText] = useState('')
  const [ticks, setTicks] = useState<boolean[]>([])
  const [checked, setChecked] = useState(false)
  const head = useRef<HTMLHeadingElement>(null)
  useEffect(() => head.current?.focus(), [])

  const num = Number(text.trim())
  const valid = text.trim() !== '' && Number.isFinite(num)
  const kv = p.key?.value ?? 0
  const numOk = valid && Math.abs(num - kv) <= (Math.abs(kv) > 1e-12 ? (item as NumericalItem).tolerance_rel * Math.abs(kv) : 1e-12)
  const unit = item.type === 'numerical' && item.unit !== '-' ? ` ${item.unit}` : ''
  const score = item.type === 'mcq' ? +(pick === item.correct_index) : item.type === 'numerical' ? +numOk : item.rubric.length ? ticks.filter(Boolean).length / item.rubric.length : 0
  const ok = item.type !== 'subjective' && score === 1

  return (
    <section className="mt-4 rounded-lg border bg-card p-4 sm:p-5">
      <p className="text-sm text-muted-foreground">Question {n} of {total} · {item.topic}</p>
      <h2 ref={head} tabIndex={-1} className="mt-1 text-lg font-semibold outline-none">{item.stem}</h2>

      {item.type === 'mcq' && (
        <fieldset disabled={checked} className="mt-3 space-y-2">
          <legend className="sr-only">Choose one answer</legend>
          {item.options.map((o, i) => (
            <label key={i} className={row}>
              <input type="radio" name="opt" className="size-5 shrink-0" checked={pick === i} onChange={() => setPick(i)} />
              <span>{o}</span>
            </label>
          ))}
        </fieldset>
      )}
      {item.type === 'numerical' && (
        <div className="mt-3">
          <label htmlFor="ans" className="block text-sm font-medium">Your answer{unit && ` (${item.unit})`}</label>
          <div className="mt-1 flex items-center gap-2">
            <input id="ans" type="text" inputMode="decimal" autoComplete="off" value={text} disabled={checked} onChange={(e) => setText(e.target.value)} placeholder="e.g. 0.667 or 1e-3" className={`${field} min-h-11 w-full max-w-xs`} />
            {unit && <span className="text-sm text-muted-foreground">{item.unit}</span>}
          </div>
        </div>
      )}
      {item.type === 'subjective' && (
        <>
          <label htmlFor="free" className="mt-3 block text-sm font-medium">Your answer</label>
          <textarea id="free" rows={5} value={text} disabled={checked} onChange={(e) => setText(e.target.value)} className={`${field} mt-1 w-full`} />
        </>
      )}

      {!checked && (
        <Button className="mt-3 w-full sm:w-auto" onClick={() => setChecked(true)} disabled={item.type === 'mcq' ? pick === undefined : item.type === 'numerical' && !valid}>
          {item.type === 'subjective' ? 'Show rubric' : 'Check'}
        </Button>
      )}

      <div aria-live="polite" className="mt-3 space-y-2 text-sm">
        {checked && item.type === 'mcq' && (
          <>
            <p className={`font-medium ${ok ? 'text-primary' : 'text-destructive'}`}>{ok ? 'Correct.' : `Incorrect. The answer is: ${item.options[item.correct_index]}`}</p>
            {!ok && <p>{item.misconceptions[String(pick)]}</p>}
            <p className="text-muted-foreground">{item.explanation}</p>
          </>
        )}
        {checked && item.type === 'numerical' && p.key && (
          <>
            <p className={`font-medium ${ok ? 'text-primary' : 'text-destructive'}`}>{ok ? 'Correct.' : `Not within ${+(item.tolerance_rel * 100).toFixed(2)}%.`}</p>
            <p>Correct value: <strong>{fmt4(p.key.value)}{unit}</strong></p>
            <p className="text-muted-foreground">{p.key.solution}</p>
          </>
        )}
        {checked && item.type === 'subjective' && (
          <fieldset>
            <legend className="font-medium">Rubric: tick what your answer covers</legend>
            <p className="text-muted-foreground">You mark this yourself. AI marking is not connected yet.</p>
            <div className="mt-2 space-y-2">
              {item.rubric.map((r, i) => (
                <label key={i} className={row}>
                  <input type="checkbox" className="size-5 shrink-0" checked={!!ticks[i]} onChange={(e) => setTicks((t) => { const c = item.rubric.map((_, j) => !!t[j]); c[i] = e.target.checked; return c })} />
                  <span>{r}</span>
                </label>
              ))}
            </div>
            <p className="mt-2 font-medium">Score: {ticks.filter(Boolean).length} of {item.rubric.length}</p>
          </fieldset>
        )}
      </div>

      {extra}
      {checked && (
        <Button className="mt-3 w-full sm:w-auto" onClick={() => onNext({ topic: item.topic, score, answer: item.type === 'mcq' ? item.options[pick!] : text })}>
          {n === total ? 'Finish' : 'Next'}
        </Button>
      )}
    </section>
  )
}

// D5 reuses this page for a prep pack: `load` replaces the fixed-topic request, `heading` the title,
// and `extra(idx)` adds a line under question idx (its notes link). Without props: the Quiz page as before.
export default function Quiz({ load, heading = 'Quiz', extra }: { load?: (onSlow: () => void) => Promise<QuizData>; heading?: string; extra?: (idx: number) => ReactNode } = {}) {
  const [prog, setProg] = useState('Loading quiz…')
  const [items, setItems] = useState<Prepared[]>()
  const [skipped, setSkipped] = useState(0)
  const [error, setError] = useState('')
  const [i, setI] = useState(0)
  const [done, setDone] = useState<Done[]>([])
  const [id, setId] = useState<string>()
  const [served, setServed] = useState(0) // item count of the quiz as served; the server wants one entry per item
  const loader = useRef(load) // the loader of the first render: a new function each render must not reload the quiz

  useEffect(() => {
    let live = true
    void warm() // boot Python while the quiz loads
    void (async () => {
      try {
        if (!loader.current && !TOPIC.trim()) throw new PlainError('Pick a topic first.') // ponytail: TOPIC is a constant today; guards the future picker
        const slow = () => setProg('Waking up the server…')
        const quiz = await (loader.current ? loader.current(slow) : getQuiz(TOPIC, slow))
        const nums = quiz.items.filter((x) => x.type === 'numerical').length
        const out: Prepared[] = []
        let skip = 0, k = 0
        for (const [idx, item] of quiz.items.entries()) {
          if (item.type !== 'numerical') { out.push({ item, idx }); continue }
          if (!live) return
          setProg(k === 0 ? 'Preparing questions… starting Python (the first run can take up to 20 s)' : `Preparing questions… checking answer key ${k + 1} of ${nums}`)
          k++
          const res = await run(item.key_code, { mode: 'solve' })
          const chk = res.ok ? checkKey(res.result, item) : undefined
          const solution = res.ok && chk?.ok ? fillSolution(item, res.result as Record<string, unknown>) : null
          if (chk?.ok && solution !== null) out.push({ item, idx, key: { value: chk.value, solution } })
          else { skip++; reportItem(quiz.id, idx, !res.ok ? `sandbox: ${res.error}` : chk && !chk.ok ? chk.reason : 'missing_placeholder') }
        }
        if (!live) return
        if (!out.length) throw new PlainError('No usable questions in this quiz.')
        setId(quiz.id); setServed(quiz.items.length); setSkipped(skip); setItems(out)
      } catch (e) {
        if (live) setError(friendly(e))
      }
    })()
    return () => { live = false }
  }, [])

  function next(d: Done) {
    const all = [...done, d]
    setDone(all)
    if (all.length < items!.length) return setI(i + 1)
    const score = all.reduce((s, x) => s + x.score, 0)
    const answers = Array<string>(served).fill(''), correct = Array<boolean | null>(served).fill(null) // null = skipped item
    all.forEach((x, k) => { const at = items![k].idx; answers[at] = x.answer; correct[at] = x.score === 1 })
    saveAnswers(id, answers, score, correct)
    try { localStorage.setItem('sf.quiz.last', JSON.stringify({ score, total: all.length, at: Date.now() })) } catch { /* private mode: results screen still works */ }
  }

  const finished = items && done.length === items.length
  const total = done.reduce((s, x) => s + x.score, 0)
  const byTopic = new Map<string, [number, number]>()
  for (const x of done) { const [s, c] = byTopic.get(x.topic) ?? [0, 0]; byTopic.set(x.topic, [s + x.score, c + 1]) }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">{heading}</h1>
      {error && <p role="alert" className="mt-3 text-sm font-medium text-destructive">{error}</p>}
      {!items && !error && <p role="status" className="mt-4 flex items-center gap-2 text-sm text-muted-foreground"><span className="size-5 shrink-0 animate-spin rounded-full border-2 border-tint border-t-primary" />{prog}</p>}
      {skipped > 0 && <p role="status" className="mt-3 rounded-lg border-2 border-warn-line bg-warn-bg p-3 text-sm text-warn">{skipped} question{skipped > 1 ? 's' : ''} skipped because their answer key failed the double-check.</p>}
      {items && !finished && <Question key={i} p={items[i]} n={i + 1} total={items.length} onNext={next} extra={extra?.(items[i].idx)} />}
      {finished && (
        <section className="mt-4 rounded-lg border bg-card p-4 sm:p-5">
          <h2 className="text-lg font-semibold">Results</h2>
          <p className="mt-1 text-3xl font-semibold tabular-nums">{+total.toFixed(1)} of {done.length}</p>
          <ul className="mt-3 space-y-1 text-sm">
            {[...byTopic].map(([t, [s, c]]) => <li key={t} className="flex justify-between gap-3"><span>{t}</span><span className="tabular-nums">{+s.toFixed(1)} of {c}</span></li>)}
          </ul>
          <Button className="mt-4 w-full sm:w-auto" onClick={() => { setI(0); setDone([]) }}>Retry quiz</Button>
        </section>
      )}
    </main>
  )
}

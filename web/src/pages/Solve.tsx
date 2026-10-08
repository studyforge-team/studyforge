import { lazy, Suspense, useEffect, useState } from 'react'
import { postResult, startSolve } from '@/api/client'
import type { Step } from '@/api/types'
import { Check, Cross } from '@/components/icons'
import { Button } from '@/components/ui/button'
import { run, warm } from '@/sandbox/client'

// Keeps react-markdown and KaTeX out of the main chunk; download starts when Solve is pressed.
const loadCard = () => import('../components/AnswerCard')
const AnswerCard = lazy(loadCard)

type Row = { code: string; stdout: string; status: 'running' | 'ok' | 'fail'; ms?: number }
const MAX_STEPS = 8
const disclose = 'inline-flex min-h-11 items-center rounded-lg px-3 text-sm text-muted-foreground hover:bg-muted hover:text-foreground aria-expanded:bg-muted aria-expanded:text-foreground'
const pre = 'mt-1 overflow-x-auto rounded-lg border bg-muted p-3 font-mono text-xs leading-relaxed'

function StepRow({ r }: { r: Row }) {
  const [open, setOpen] = useState<'code' | 'out'>()
  const toggle = (k: 'code' | 'out') => setOpen(open === k ? undefined : k)
  const label = r.status === 'running' ? 'Running Python' : r.status === 'ok' ? 'Ran Python' : 'Python failed'
  const tone = r.status === 'ok' ? 'bg-primary text-primary-foreground' : r.status === 'fail' ? 'bg-destructive text-primary-foreground' : 'bg-card'
  return (
    <li className="relative pl-10">
      <span aria-hidden="true" className={`absolute left-0 top-1 flex size-6 items-center justify-center rounded-full ${tone}`}>
        {r.status === 'ok' ? <Check width={14} height={14} /> : r.status === 'fail' ? <Cross width={14} height={14} /> : <span className="size-5 animate-spin rounded-full border-2 border-tint border-t-primary" />}
      </span>
      <div className="flex min-h-8 items-center justify-between gap-3 text-sm">
        <p className="font-medium">{label} <span className="font-normal text-muted-foreground">· network blocked</span></p>
        {r.status === 'ok' && <span className="shrink-0 tabular-nums text-muted-foreground">{r.ms} ms</span>}
      </div>
      <div className="flex flex-wrap gap-1">
        <button type="button" className={disclose} aria-expanded={open === 'code'} onClick={() => toggle('code')}>Show code</button>
        {r.stdout && <button type="button" className={disclose} aria-expanded={open === 'out'} onClick={() => toggle('out')}>Output</button>}
      </div>
      {open === 'code' && <pre className={pre}>{r.code}</pre>}
      {open === 'out' && <pre className={pre}>{r.stdout}</pre>}
    </li>
  )
}

export default function Solve() {
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)
  const [rows, setRows] = useState<Row[]>([])
  const [end, setEnd] = useState<Step>()
  const [error, setError] = useState('')
  const [slow, setSlow] = useState(false)

  useEffect(() => { void warm() }, []) // boot the sandbox while the student types

  const patch = (i: number, p: Partial<Row>) => setRows((r) => r.map((x, j) => (j === i ? { ...x, ...p } : x)))

  async function submit() {
    if (busy || !question.trim()) return
    setBusy(true); setRows([]); setEnd(undefined); setError(''); setSlow(false)
    void loadCard() // fire and forget: fetch the answer-card chunk while Python runs
    const onSlow = () => setSlow(true)
    try {
      const first = await startSolve(question, onSlow)
      let step = first.step
      for (let n = 0; step.type === 'run_python'; n++) {
        if (n >= MAX_STEPS) throw new Error('Too many steps, stopping.')
        const { code } = step
        setRows((r) => [...r, { code, stdout: '', status: 'running' }])
        const res = await run(code, { mode: 'solve' })
        const body = res.ok
          ? { stdout: res.stdout, result: res.result, figures: res.figures, error: null, ms: res.ms }
          : { stdout: '', result: null, figures: [], error: res.error, ms: 0 }
        patch(n, { status: res.ok ? 'ok' : 'fail', ms: body.ms, stdout: body.stdout })
        step = await postResult(first.solve_id, body, onSlow)
      }
      setEnd(step)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
    } finally {
      setBusy(false); setSlow(false)
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="print:hidden text-2xl font-semibold tracking-tight">Ask a question</h1>
      <div className="mt-4 rounded-lg border bg-card p-4 print:hidden sm:p-5">
        <label htmlFor="q" className="block text-sm font-medium">Your question</label>
        <p id="q-help" className="mt-1 text-sm text-muted-foreground">Ask anything from your course — numbers are computed, not guessed.</p>
        <textarea
          id="q" rows={4} value={question} disabled={busy} aria-describedby="q-help"
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit() }}
          className="mt-3 w-full rounded-lg border border-input bg-background p-3 text-base placeholder:text-muted-foreground disabled:opacity-60"
          placeholder="e.g. Conversion in a CSTR for a first-order reaction, k = 0.2 1/min, tau = 10 min"
        />
        <Button className="mt-3 w-full sm:w-auto" onClick={() => void submit()} disabled={busy || !question.trim()}>
          {busy ? 'Solving…' : 'Solve'}
        </Button>
        {slow && <p className="mt-2 text-sm text-muted-foreground">Waking up the server…</p>}
      </div>
      {error && <p role="alert" className="mt-3 text-sm font-medium text-destructive">{error}</p>}
      <div aria-live="polite" className="mt-4 print:hidden">
        {rows.length > 0 && (
          <ol className="relative space-y-3 rounded-lg border bg-card p-4 before:absolute before:bottom-8 before:left-[27px] before:top-8 before:w-px before:bg-border">
            {rows.map((r, i) => <StepRow key={i} r={r} />)}
          </ol>
        )}
        {end?.type === 'need_confirm' && (
          <div className="mt-3 rounded-lg border-2 border-warn-line bg-warn-bg p-4 text-sm">
            <pre className="whitespace-pre-wrap break-words">{end.extracted_text}</pre>
            <p className="mt-2 text-warn">Confirm screen (S5) goes here</p>
          </div>
        )}
      </div>
      {end?.type === 'final' && (
        <>
        <p className="mt-4 hidden whitespace-pre-wrap print:block">{question}</p>
        <Suspense fallback={<p className="mt-6 text-sm text-muted-foreground">Loading answer…</p>}>
          <AnswerCard a={end} ran={rows.length > 0 && rows.every((r) => r.status === 'ok')} />
        </Suspense>
        </>
      )}
    </main>
  )
}

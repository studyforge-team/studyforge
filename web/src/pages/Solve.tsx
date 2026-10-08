import { lazy, Suspense, useEffect, useState } from 'react'
import { postResult, startSolve } from '@/api/client'
import type { Step } from '@/api/types'
import { Button } from '@/components/ui/button'
import { run, warm } from '@/sandbox/client'

// Keeps react-markdown and KaTeX out of the main chunk; download starts when Solve is pressed.
const loadCard = () => import('../components/AnswerCard')
const AnswerCard = lazy(loadCard)

type Row = { code: string; stdout: string; status: 'running' | 'ok' | 'fail'; ms?: number }
const MAX_STEPS = 8

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
    <main className="mx-auto max-w-2xl px-4 py-8">
      <a href="#" className="print:hidden text-sm underline">← Today</a>
      <h1 className="print:hidden mt-2 text-2xl font-bold tracking-tight">StudyForge</h1>
      <label htmlFor="q" className="mt-4 block print:hidden text-sm font-medium">Your question</label>
      <textarea
        id="q" rows={4} value={question} disabled={busy}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) void submit() }}
        className="mt-1 w-full rounded-md border bg-background p-2 text-base print:hidden"
        placeholder="e.g. Conversion in a CSTR for a first-order reaction, k = 0.2 1/min, tau = 10 min"
      />
      <Button className="mt-2 print:hidden" onClick={() => void submit()} disabled={busy || !question.trim()}>
        {busy ? 'Solving…' : 'Solve'}
      </Button>
      {slow && <p className="mt-2 text-sm text-muted-foreground print:hidden">Waking up the server…</p>}
      {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      <div aria-live="polite" className="mt-4 space-y-2 print:hidden">
        {rows.map((r, i) => (
          <div key={i} className="rounded border p-2 text-sm">
            <p>
              {r.status === 'running' ? 'Running Python (network: blocked)…' : r.status === 'ok' ? `✓ Ran Python (${r.ms} ms)` : '✗ Python failed'}
            </p>
            <details><summary className="cursor-pointer">Show code</summary><pre className="overflow-x-auto bg-muted p-2 text-xs">{r.code}</pre></details>
            {r.stdout && <details><summary className="cursor-pointer">Output</summary><pre className="overflow-x-auto bg-muted p-2 text-xs">{r.stdout}</pre></details>}
          </div>
        ))}
        {end?.type === 'need_confirm' && (
          <div className="rounded border-2 p-3 text-sm">
            <pre className="whitespace-pre-wrap break-words">{end.extracted_text}</pre>
            <p className="mt-2 text-muted-foreground">Confirm screen (S5) goes here</p>
          </div>
        )}
      </div>
      {end?.type === 'final' && (
        <>
        <p className="mt-4 hidden whitespace-pre-wrap print:block">{question}</p>
        <Suspense fallback={<p>Loading answer…</p>}>
          <AnswerCard a={end} />
        </Suspense>
        </>
      )}
    </main>
  )
}

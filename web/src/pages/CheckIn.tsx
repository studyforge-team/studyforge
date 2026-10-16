import { useEffect, useState } from 'react'
import { answerCheckin, getDashboard, getPrep } from '@/api/client'
import type { CheckinResult, MCQItem } from '@/api/types'
import { Button } from '@/components/ui/button'
import { friendly, HttpError } from '@/lib/errors'

const row = 'flex min-h-11 items-center gap-3 rounded-lg border p-3 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:checked]:border-primary'

function outcome(r: CheckinResult) {
  if (r.done) return 'Marked done. Reminders for this task are stopped.'
  return r.follow_up_at ? `We'll check in again ${new Date(r.follow_up_at).toLocaleString()}.` : 'That was the last check-in for this task.'
}

export default function CheckIn({ jobId }: { jobId: string }) {
  const [title, setTitle] = useState('')
  const [q, setQ] = useState<MCQItem | null | undefined>() // undefined = loading, null = no question (self-report)
  const [pick, setPick] = useState<number>()
  const [sent, setSent] = useState<boolean>() // the answer being/was submitted
  const [msg, setMsg] = useState('')
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    void (async () => {
      const t = await getDashboard().then((d) => d.reminders.find((r) => r.id === jobId)?.title.match(/^Did you finish (.+?)\? Answer one quick question/)?.[1]).catch(() => undefined) || 'this task'
      // D5: the question comes from this task's prep pack (the check-in link carries its key)
      const key = /^#prep\/([0-9a-f]{16})\?/.exec(location.hash)?.[1]
      const item = key ? await getPrep(key).then((p) => p.quiz.items.find((x): x is MCQItem => x.type === 'mcq') ?? null).catch(() => null) : null
      if (live) { setTitle(t); setQ(item) }
    })()
    return () => { live = false }
  }, [jobId])

  async function send(correct: boolean) {
    setSent(correct); setFailed(false); setMsg('')
    try { setMsg(outcome(await answerCheckin(jobId, correct))) } catch (e) {
      const s = e instanceof HttpError ? e.status : 0
      if (s === 409) setMsg('This check-in was already answered.')
      else if (s === 404) setMsg('This check-in no longer exists.')
      else { setMsg(friendly(e)); setFailed(true) }
    }
  }

  const ok = q ? pick === q.correct_index : false
  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">{q === undefined ? 'Check-in' : `Check-in: ${title}`}</h1>
      {q === undefined && <p role="status" className="mt-4 text-sm text-muted-foreground">Loading your question…</p>}
      {q === null && sent === undefined && (
        <section className="mt-4 rounded-lg border bg-card p-4 sm:p-5">
          <p>Couldn't load a question, so this one is on your word: did you finish it?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button className="min-h-11" onClick={() => void send(true)}>Yes, done</Button>
            <Button variant="outline" className="min-h-11" onClick={() => void send(false)}>Not yet</Button>
          </div>
        </section>
      )}
      {q && (
        <section className="mt-4 rounded-lg border bg-card p-4 sm:p-5">
          <h2 className="text-lg font-semibold">{q.stem}</h2>
          <fieldset disabled={sent !== undefined} className="mt-3 space-y-2">
            <legend className="sr-only">Choose one answer</legend>
            {q.options.map((o, i) => (
              <label key={i} className={row}>
                <input type="radio" name="opt" className="size-5 shrink-0" checked={pick === i} onChange={() => setPick(i)} />
                <span>{o}</span>
              </label>
            ))}
          </fieldset>
          {sent === undefined && <Button className="mt-3 min-h-11 w-full sm:w-auto" disabled={pick === undefined} onClick={() => void send(ok)}>Check</Button>}
          <div aria-live="polite" className="mt-3 space-y-2 text-sm">
            {sent !== undefined && (
              <>
                <p className={`font-medium ${ok ? 'text-primary' : 'text-destructive'}`}>{ok ? 'Correct.' : `Incorrect. The answer is: ${q.options[q.correct_index]}`}</p>
                {!ok && <p>{q.misconceptions[String(pick)]}</p>}
                <p className="text-muted-foreground">{q.explanation}</p>
              </>
            )}
          </div>
        </section>
      )}
      {sent !== undefined && (
        <div className="mt-4 space-y-3">
          {!msg && <p role="status" className="text-sm text-muted-foreground">Saving…</p>}
          {msg && <p role={failed ? 'alert' : 'status'} className={`text-sm font-medium ${failed ? 'text-destructive' : ''}`}>{msg}</p>}
          {failed && <Button className="min-h-11" onClick={() => void send(sent)}>Retry</Button>}
          {msg && !failed && <a href="#" className="inline-flex min-h-11 items-center text-primary underline">Back to Today</a>}
        </div>
      )}
    </main>
  )
}

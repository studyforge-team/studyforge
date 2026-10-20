import { lazy, Suspense, useEffect, useState } from 'react'
import { getSolves, getSolveStep } from '@/api/client'
import type { SolveItem, Step } from '@/api/types'
import { Button } from '@/components/ui/button'
import { friendly, HttpError } from '@/lib/errors'

const AnswerCard = lazy(() => import('@/components/AnswerCard')) // keeps markdown/KaTeX out of the list's chunk
const wrap = 'mx-auto max-w-3xl px-4 py-6 sm:py-8'
const ID = /^#history\/([^/?#]+)/

const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
function group(iso: string): string {
  const days = Math.round((day(new Date()) - day(new Date(iso))) / 86_400_000)
  return days <= 0 ? 'Today' : days === 1 ? 'Yesterday' : days < 7 ? 'Last 7 days' : 'Older'
}
const ORDER = ['Today', 'Yesterday', 'Last 7 days', 'Older']

function Detail({ id }: { id: string }) {
  const [res, setRes] = useState<{ step?: Step; err?: string } | null>(null)
  useEffect(() => {
    let live = true
    getSolveStep(decodeURIComponent(id)).then(
      (step) => live && setRes({ step }),
      (e: unknown) => live && setRes({ err: e instanceof HttpError && e.status === 404 ? 'Not found.' : friendly(e) }),
    )
    return () => { live = false }
  }, [id])
  return (
    <main className={wrap}>
      <a href="#history" className="inline-flex min-h-11 items-center text-sm font-medium text-primary">← All history</a>
      <h1 className="text-2xl font-semibold tracking-tight">Past solve</h1>
      {!res && <p role="status" className="mt-4 text-sm text-muted-foreground">Loading…</p>}
      {res?.err && <p role="alert" className="mt-4 text-sm font-medium text-destructive">{res.err}</p>}
      {res?.step?.type === 'final' && <Suspense fallback={null}><AnswerCard a={res.step} /></Suspense>}
      {res?.step && res.step.type !== 'final' && <p className="mt-4 text-sm text-muted-foreground">This solve did not finish.</p>}
    </main>
  )
}

function List() {
  const [input, setInput] = useState('')
  const [q, setQ] = useState('') // the search that was sent: input after 300 ms of quiet
  const [items, setItems] = useState<SolveItem[]>([])
  const [next, setNext] = useState<string | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'more'>('loading')
  const [err, setErr] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setQ(input.trim()), 300)
    return () => clearTimeout(t)
  }, [input])

  useEffect(() => {
    let live = true
    getSolves(null, q).then(
      (r) => { if (live) { setItems(r.items); setNext(r.next); setErr(''); setState('ready') } },
      (e: unknown) => { if (live) { setItems([]); setNext(null); setErr(friendly(e)); setState('ready') } },
    )
    return () => { live = false }
  }, [q])

  const more = () => {
    setState('more')
    getSolves(next, q).then(
      (r) => { setItems((a) => [...a, ...r.items]); setNext(r.next); setErr(''); setState('ready') },
      (e: unknown) => { setErr(friendly(e)); setState('ready') },
    )
  }

  return (
    <main className={wrap}>
      <h1 className="text-2xl font-semibold tracking-tight">History</h1>
      <input
        type="search" aria-label="Search your questions" placeholder="Search your questions" maxLength={80}
        value={input} onChange={(e) => setInput(e.target.value)}
        className="mt-4 min-h-11 w-full rounded-lg border border-input bg-background px-3 py-2 text-base"
      />
      {err && <p role="alert" className="mt-4 text-sm font-medium text-destructive">{err}</p>}
      {state === 'loading' && <p role="status" className="mt-4 text-sm text-muted-foreground">Loading…</p>}
      {state !== 'loading' && !err && items.length === 0 && (
        <p className="mt-4 text-sm text-muted-foreground">{q ? 'No questions match.' : 'No solves yet. Ask your first question.'}</p>
      )}
      {ORDER.map((g) => {
        const rows = items.filter((s) => group(s.updated_at) === g)
        return rows.length > 0 && (
          <section key={g} aria-label={g} className="mt-6">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{g}</h2>
            <ul className="mt-2 divide-y rounded-lg border bg-card">
              {rows.map((s) => (
                <li key={s.id}>
                  <a href={`#history/${encodeURIComponent(s.id)}`} className="block min-h-11 px-3 py-2 text-sm hover:bg-muted">
                    <p className="line-clamp-2 break-words">{s.question || 'Untitled question'}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(s.updated_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}
                      {s.status && s.status !== 'done' ? ' · not finished' : ''}
                    </p>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )
      })}
      {next && <Button variant="outline" className="mt-4 min-h-11" disabled={state === 'more'} onClick={more}>{state === 'more' ? 'Loading…' : 'Load more'}</Button>}
    </main>
  )
}

// T5: #history = the student's past questions, newest first; #history/<id> = one answer again.
export default function History() {
  const id = ID.exec(location.hash)?.[1]
  return id ? <Detail id={id} /> : <List />
}

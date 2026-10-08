import { useEffect, useRef, useState, type ReactNode } from 'react'
import { getDashboard } from '@/api/client'
import type { Dashboard as Data } from '@/api/types'
import { Button } from '@/components/ui/button'
import { warm } from '@/sandbox/client'

const KEY = 'sf-seen-reminders'
const H = 3_600_000
const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
const dtf = new Intl.DateTimeFormat('en', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function rel(iso: string) {
  const ms = new Date(iso).getTime() - Date.now()
  const a = Math.abs(ms)
  return a < H ? rtf.format(Math.round(ms / 60_000), 'minute') : a < 48 * H ? rtf.format(Math.round(ms / H), 'hour') : rtf.format(Math.round(ms / (24 * H)), 'day')
}

// ponytail: per-device seen state until the server tracks it
function loadSeen(): string[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') as string[] } catch { return [] }
}

const Card = ({ title, empty, children }: { title: string; empty: string; children: ReactNode[] }) => (
  <section className="rounded-lg border bg-card p-4">
    <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</h2>
    {children.length ? <ul className="mt-3 space-y-3">{children}</ul> : <p className="mt-3 text-sm text-muted-foreground">{empty}</p>}
  </section>
)

const Chip = ({ children }: { children: ReactNode }) => <span className="inline-flex items-center rounded-full bg-tint px-3 py-1 text-sm font-medium text-primary">{children}</span>
const Shade = ({ className }: { className: string }) => <div className={`animate-pulse rounded-lg bg-muted ${className}`} />
const wrap = 'mx-auto max-w-3xl px-4 py-6 sm:py-8'

export default function Dashboard() {
  const [data, setData] = useState<Data>()
  const [error, setError] = useState(false)
  const [tries, setTries] = useState(0)
  const [now] = useState(Date.now)
  const [seen] = useState(loadSeen) // read once, so "New" badges stay until the next visit
  const inboxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const c = (navigator as { connection?: { saveData?: boolean; effectiveType?: string } }).connection
    if (!c?.saveData && c?.effectiveType !== 'slow-2g' && c?.effectiveType !== '2g') void warm()
  }, [])

  useEffect(() => {
    getDashboard().then(setData, () => setError(true))
  }, [tries])

  // ponytail: seen = inbox was on screen ≥1 s; per-device until the server tracks it
  useEffect(() => {
    const el = inboxRef.current
    if (!data || !el) return
    let timer: ReturnType<typeof setTimeout> | undefined
    const io = new IntersectionObserver(([entry]) => {
      clearTimeout(timer)
      if (!entry.isIntersecting) return
      timer = setTimeout(() => {
        try {
          const ids = new Set([...loadSeen(), ...data.reminders.filter((r) => r.sent_at).map((r) => r.id)])
          localStorage.setItem(KEY, JSON.stringify([...ids]))
        } catch { /* storage blocked */ }
        io.disconnect()
      }, 1000)
    }, { threshold: 0.5 })
    io.observe(el)
    return () => {
      clearTimeout(timer)
      io.disconnect()
    }
  }, [data])

  if (error) {
    return (
      <main className={wrap}>
        <p role="alert" className="text-sm font-medium text-destructive">Couldn't load your dashboard.</p>
        <Button className="mt-2" onClick={() => { setError(false); setTries(tries + 1) }}>Retry</Button>
      </main>
    )
  }
  if (!data) {
    return (
      <main className={wrap} aria-busy="true">
        <p role="status" className="sr-only">Loading your dashboard…</p>
        <Shade className="h-4 w-40" />
        <Shade className="mt-4 h-48" />
        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2"><Shade className="h-32" /><Shade className="h-32" /></div>
      </main>
    )
  }

  const open = data.tasks.filter((t) => t.status === 'open').sort((a, b) => a.due_at_utc.localeCompare(b.due_at_utc))
  const soon = open.filter((t) => new Date(t.due_at_utc).getTime() - now < 48 * H)
  const weak = data.weak_topics[0]
  const fired = data.reminders.filter((r) => r.sent_at).sort((a, b) => b.sent_at!.localeCompare(a.sent_at!))
  const upcoming = data.reminders.filter((r) => !r.sent_at).sort((a, b) => a.due_at_utc.localeCompare(b.due_at_utc))
  const fresh = fired.filter((r) => !seen.includes(r.id)).length

  return (
    <main className={wrap}>
      <h1 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">What do I do today?</h1>
      <section aria-label="Today" className="sf-in mt-3 rounded-lg border border-primary/40 bg-card p-5 sm:p-6">
        <h2 className="text-2xl font-semibold leading-snug tracking-tight sm:text-3xl">
          {soon.length ? <>{soon[0].title} <span className="whitespace-nowrap font-normal text-muted-foreground">· due {rel(soon[0].due_at_utc)}</span></> : 'Nothing due in the next 48 hours.'}
        </h2>
        {soon.length > 1 && (
          <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
            {soon.slice(1).map((t) => <li key={t.id}><span className="font-medium text-foreground">{t.title}</span> · due {rel(t.due_at_utc)}</li>)}
          </ul>
        )}
        {(weak || fresh > 0) && (
          <div className="mt-4 flex flex-wrap gap-2">
            {weak && <Chip>Practise next: {weak.topic} ({weak.correct}/{weak.attempts} correct)</Chip>}
            {fresh > 0 && <Chip>{fresh} new reminder{fresh > 1 ? 's' : ''}</Chip>}
          </div>
        )}
        <Button className="mt-5 w-full sm:w-auto" onClick={() => { location.hash = '#solve' }}>Ask a question</Button>
      </section>

      {/* ponytail: prep-pack link lands with D5 */}
      <div className="mt-4 grid grid-cols-1 items-start gap-4 md:grid-cols-2">
        <Card title="Deadlines" empty="No open deadlines.">
          {open.map((t) => (
            <li key={t.id} className="text-sm"><span className="font-medium">{t.title}</span><br /><span className="tabular-nums text-muted-foreground">{dtf.format(new Date(t.due_at_utc))} · {rel(t.due_at_utc)}</span></li>
          ))}
        </Card>
        <Card title="Weak topics" empty="No weak topics yet. Solve a few questions first.">
          {data.weak_topics.map((w) => (
            <li key={w.topic} className="text-sm">
              <div className="flex justify-between gap-2"><span>{w.topic}</span><span className="shrink-0 tabular-nums text-muted-foreground">{w.correct}/{w.attempts}</span></div>
              <div aria-hidden="true" className="mt-1.5 h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${Math.round((w.correct / w.attempts) * 100)}%` }} /></div>
            </li>
          ))}
        </Card>
        {/* ponytail: no GET /solve/{id} in the contract yet, so recent solves are not links */}
        <Card title="Recent solves" empty="No solves yet. Ask your first question.">
          {data.recent_solves.map((s) => (
            <li key={s.id} className="text-sm"><p className="truncate">{s.question}</p><p className="text-muted-foreground">{rel(s.created_at)}</p></li>
          ))}
        </Card>
        <div ref={inboxRef} role="region" aria-label="Reminders inbox">
          <Card title="Reminders inbox" empty="No reminders yet.">
            {[...fired, ...upcoming].map((r) => (
              <li key={r.id} className="text-sm">
                <p className="flex items-start gap-2">
                  {r.sent_at && !seen.includes(r.id) && <span className="mt-0.5 inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-primary"><span aria-hidden="true" className="size-2 rounded-full bg-primary" />New</span>}
                  <span>{r.title}</span>
                </p>
                <p className="text-muted-foreground">
                  {r.sent_at ? `Sent ${rel(r.sent_at)}` : `Scheduled ${rel(r.due_at_utc)}`} · {r.channel === 'telegram' ? 'Telegram' : 'In app'}
                </p>
              </li>
            ))}
          </Card>
        </div>
      </div>
    </main>
  )
}

import { useEffect, useState, type ReactNode } from 'react'
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
  <section className="mt-4 rounded-lg border p-4">
    <h2 className="text-base font-semibold">{title}</h2>
    {children.length ? <ul className="mt-2 space-y-2">{children}</ul> : <p className="mt-2 text-sm text-muted-foreground">{empty}</p>}
  </section>
)

export default function Dashboard() {
  const [data, setData] = useState<Data>()
  const [error, setError] = useState(false)
  const [tries, setTries] = useState(0)
  const [now] = useState(Date.now)
  const [seen] = useState(loadSeen) // read once, so "New" badges stay until the next visit

  useEffect(() => {
    const c = (navigator as { connection?: { saveData?: boolean; effectiveType?: string } }).connection
    if (!c?.saveData && c?.effectiveType !== 'slow-2g' && c?.effectiveType !== '2g') void warm()
  }, [])

  useEffect(() => {
    getDashboard().then(setData, () => setError(true))
  }, [tries])

  useEffect(() => {
    if (!data) return
    const t = setTimeout(() => {
      try { localStorage.setItem(KEY, JSON.stringify(data.reminders.filter((r) => r.sent_at).map((r) => r.id))) } catch { /* storage blocked */ }
    }, 3000)
    return () => clearTimeout(t)
  }, [data])

  if (error) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8">
        <p role="alert" className="text-sm text-red-700">Couldn't load your dashboard.</p>
        <Button className="mt-2" onClick={() => { setError(false); setTries(tries + 1) }}>Retry</Button>
      </main>
    )
  }
  if (!data) return <main className="mx-auto max-w-2xl px-4 py-8"><p className="text-sm text-muted-foreground">Loading your dashboard…</p></main>

  const open = data.tasks.filter((t) => t.status === 'open').sort((a, b) => a.due_at_utc.localeCompare(b.due_at_utc))
  const soon = open.filter((t) => new Date(t.due_at_utc).getTime() - now < 48 * H)
  const weak = data.weak_topics[0]
  const fired = data.reminders.filter((r) => r.sent_at).sort((a, b) => b.sent_at!.localeCompare(a.sent_at!))
  const upcoming = data.reminders.filter((r) => !r.sent_at).sort((a, b) => a.due_at_utc.localeCompare(b.due_at_utc))
  const fresh = fired.filter((r) => !seen.includes(r.id)).length

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold tracking-tight">What do I do today?</h1>
      <section aria-label="Today" className="mt-4 rounded-lg border-2 p-4 text-sm">
        <p className="font-medium">
          {soon.length ? `Due soon: ${soon.map((t) => `${t.title} (${rel(t.due_at_utc)})`).join('; ')}` : 'Nothing due in the next 48 hours.'}
        </p>
        {weak && <p className="mt-1">Practise next: {weak.topic} ({weak.correct}/{weak.attempts} correct)</p>}
        {fresh > 0 && <p className="mt-1">{fresh} new reminder{fresh > 1 ? 's' : ''}</p>}
        <Button className="mt-3" onClick={() => { location.hash = '#solve' }}>Ask a question</Button>
      </section>

      {/* ponytail: prep-pack link lands with D5 */}
      <Card title="Deadlines" empty="No open deadlines.">
        {open.map((t) => (
          <li key={t.id} className="text-sm"><span className="font-medium">{t.title}</span><br /><span className="text-muted-foreground">{dtf.format(new Date(t.due_at_utc))} · {rel(t.due_at_utc)}</span></li>
        ))}
      </Card>
      <Card title="Weak topics" empty="No weak topics yet. Solve a few questions first.">
        {data.weak_topics.map((w) => (
          <li key={w.topic} className="text-sm">
            <div className="flex justify-between gap-2"><span>{w.topic}</span><span className="shrink-0 text-muted-foreground">{w.correct}/{w.attempts}</span></div>
            <div className="mt-1 h-2 rounded bg-muted"><div className="h-2 rounded bg-primary" style={{ width: `${Math.round((w.correct / w.attempts) * 100)}%` }} /></div>
          </li>
        ))}
      </Card>
      {/* ponytail: no GET /solve/{id} in the contract yet, so recent solves are not links */}
      <Card title="Recent solves" empty="No solves yet. Ask your first question.">
        {data.recent_solves.map((s) => (
          <li key={s.id} className="text-sm"><p className="truncate">{s.question}</p><p className="text-muted-foreground">{rel(s.created_at)}</p></li>
        ))}
      </Card>
      <div role="region" aria-label="Reminders inbox">
        <Card title="Reminders inbox" empty="No reminders yet.">
          {[...fired, ...upcoming].map((r) => (
            <li key={r.id} className="text-sm">
              <p>
                {r.sent_at && !seen.includes(r.id) && <span className="mr-2 rounded bg-primary px-1.5 py-0.5 text-xs text-primary-foreground">New</span>}
                {r.title}
              </p>
              <p className="text-muted-foreground">
                {r.sent_at ? `Sent ${rel(r.sent_at)}` : `Scheduled ${rel(r.due_at_utc)}`} · {r.channel === 'telegram' ? 'Telegram' : 'In app'}
              </p>
            </li>
          ))}
        </Card>
      </div>
    </main>
  )
}

import { useEffect, useState } from 'react'
import { getQuizAttempts } from '@/api/client'
import type { QuizAttempt, QuizAttempts } from '@/api/types'
import { LineChart } from '@/components/LineChart'

const pct = (a: QuizAttempt) => (a.total > 0 ? Math.round((a.score / a.total) * 100) : 0) // score/total are item counts; marks scale both sides
const marks = (n: number) => +n.toFixed(1)
const day = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

// Last attempt against the mean of the ones before it: more than 5 points either way is a trend.
function trend(attempts: QuizAttempt[]): 'improving' | 'dropping' | 'steady' | null {
  if (attempts.length < 2) return null
  const prev = attempts.slice(0, -1).map(pct)
  const d = pct(attempts[attempts.length - 1]) - prev.reduce((s, x) => s + x, 0) / prev.length
  return d > 5 ? 'improving' : d < -5 ? 'dropping' : 'steady'
}

// T4 "My progress". Shown only when the server returns attempts: signed out (401), demo mode and no attempts all render nothing.
export function QuizProgress() {
  const [data, setData] = useState<QuizAttempts>()
  useEffect(() => {
    let live = true
    getQuizAttempts().then((d) => live && setData(d), () => {})
    return () => { live = false }
  }, [])
  if (!data?.topics.length) return null
  return (
    <section aria-labelledby="progress-h" className="mt-4">
      <h2 id="progress-h" className="text-lg font-semibold">My progress</h2>
      <div className="mt-2 space-y-3">
        {data.topics.map((t) => {
          const tr = trend(t.attempts)
          return (
            <article key={t.topic} className="rounded-lg border bg-card p-4">
              <h3 className="flex flex-wrap items-baseline justify-between gap-x-3 font-medium">
                <span>{t.topic}</span>
                {tr && <span className={`text-sm ${tr === 'dropping' ? 'text-destructive' : tr === 'improving' ? 'text-primary' : 'text-muted-foreground'}`}>{tr}</span>}
              </h3>
              <ul className="mt-2 space-y-1 text-sm">
                {t.attempts.map((a, i) => (
                  <li key={i} className="tabular-nums">{marks(a.score * a.marks_per_q)} / {marks(a.total * a.marks_per_q)} marks ({pct(a)} %) · {day(a.created_at)}</li>
                ))}
              </ul>
              {t.attempts.length >= 2 && (
                <div className="mt-3">
                  <LineChart title={`${t.topic}: score per attempt`} xLabel="attempt" yLabel="%"
                    lines={[{ name: 'Score %', x: t.attempts.map((_, i) => i + 1), y: t.attempts.map(pct), color: 'var(--primary)' }]} />
                </div>
              )}
            </article>
          )
        })}
      </div>
    </section>
  )
}

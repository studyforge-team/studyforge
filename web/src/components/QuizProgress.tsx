import { useEffect, useState } from 'react'
import { LineChart } from '@/components/LineChart'
import { getQuizAttempts } from '@/api/client'
import type { QuizAttemptsResponse } from '@/api/types'

const demo = !import.meta.env.VITE_API_URL
const dtShort = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' })

export function QuizProgress() {
  const [attempts, setAttempts] = useState<QuizAttemptsResponse | null>(null)
  useEffect(() => {
    if (demo) return
    getQuizAttempts().then(setAttempts).catch(() => {})
  }, [])

  if (demo || !attempts || !attempts.topics.length) return null

  return (
    <section className="mb-6 rounded-lg border bg-card p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        My progress
      </h2>
      <div className="mt-3 space-y-4">
        {attempts.topics.map((t) => {
          const pcts = t.attempts.map((a) =>
            a.total > 0 ? (a.score / a.total) * 100 : 0,
          )
          const lastPct = pcts.at(-1) ?? 0
          const prevMean =
            pcts.length > 1
              ? pcts.slice(0, -1).reduce((s, v) => s + v, 0) / (pcts.length - 1)
              : null
          const trend =
            prevMean === null
              ? null
              : lastPct - prevMean > 5
                ? 'improving'
                : lastPct - prevMean < -5
                  ? 'dropping'
                  : 'steady'

          return (
            <div key={t.topic} className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{t.topic}</h3>
                {trend && (
                  <span
                    className={`text-xs font-medium ${trend === 'improving' ? 'text-green-600' : trend === 'dropping' ? 'text-red-500' : 'text-muted-foreground'}`}
                  >
                    {trend === 'improving' ? '↑' : trend === 'dropping' ? '↓' : '→'} {trend}
                  </span>
                )}
              </div>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {t.attempts.map((a, i) => {
                  const marks = Math.round(a.score * a.marks_per_q)
                  const totalMarks = Math.round(a.total * a.marks_per_q)
                  const pct = a.total > 0 ? Math.round((a.score / a.total) * 100) : 0
                  const date = a.created_at ? dtShort.format(new Date(a.created_at)) : ''
                  return (
                    <li key={i}>
                      {marks} / {totalMarks} marks ({pct} %) · {date}
                    </li>
                  )
                })}
              </ul>
              {pcts.length >= 2 && (
                <LineChart
                  title=""
                  lines={[{ label: t.topic, values: pcts }]}
                  xLabel="Attempt"
                  yLabel="%"
                />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default QuizProgress

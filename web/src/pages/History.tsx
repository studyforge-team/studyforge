import { lazy, Suspense, useEffect, useState } from 'react'
import { getSolves } from '@/api/client'
import type { SolveItem, Step } from '@/api/types'
import { Button } from '@/components/ui/button'

const loadCard = () => import('../components/AnswerCard')
const AnswerCard = lazy(loadCard)

const BASE = import.meta.env.VITE_API_URL as string | undefined
const demo = !BASE
const wrap = 'mx-auto max-w-3xl px-4 py-6 sm:py-8'

type GroupedSolves = {
  today: SolveItem[]
  yesterday: SolveItem[]
  last7Days: SolveItem[]
  older: SolveItem[]
}

function groupSolves(items: SolveItem[]): GroupedSolves {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000
  const sevenDaysStart = todayStart - 7 * 24 * 60 * 60 * 1000

  const groups: GroupedSolves = {
    today: [],
    yesterday: [],
    last7Days: [],
    older: [],
  }

  for (const item of items) {
    if (!item.updated_at) {
      groups.older.push(item)
      continue
    }
    const time = new Date(item.updated_at).getTime()
    if (isNaN(time)) {
      groups.older.push(item)
    } else if (time >= todayStart) {
      groups.today.push(item)
    } else if (time >= yesterdayStart) {
      groups.yesterday.push(item)
    } else if (time >= sevenDaysStart) {
      groups.last7Days.push(item)
    } else {
      groups.older.push(item)
    }
  }

  return groups
}

export default function History() {
  const [items, setItems] = useState<SolveItem[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [activeSolveId, setActiveSolveId] = useState<string | null>(null)
  const [activeStep, setActiveStep] = useState<Step | null>(null)
  const [stepLoading, setStepLoading] = useState(false)
  const [stepError, setStepError] = useState<string | null>(null)

  // Track sub-hash for #history/<id>
  useEffect(() => {
    const handleHash = () => {
      const match = location.hash.match(/^#history\/([^/?#]+)/)
      if (match) {
        setActiveSolveId(match[1])
      } else {
        setActiveSolveId(null)
      }
    }
    handleHash()
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  // Fetch solve details when activeSolveId changes
  useEffect(() => {
    if (!activeSolveId) return

    if (demo) {
      const timer = setTimeout(() => {
        setStepError('Demo mode — cannot load individual solve from server.')
      }, 0)
      return () => clearTimeout(timer)
    }

    let ignore = false
    queueMicrotask(() => {
      if (!ignore) setStepLoading(true)
    })

    fetch(`${BASE}/api/v1/solve/${activeSolveId}`)
      .then(async (r) => {
        if (r.status === 404) throw new Error('Not found.')
        if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
        const data = await r.json()
        if (!ignore) {
          setActiveStep(data.step)
          setStepError(null)
        }
      })
      .catch((err) => {
        if (!ignore) {
          setStepError(err instanceof Error ? err.message : 'Error loading solve')
          setActiveStep(null)
        }
      })
      .finally(() => {
        if (!ignore) setStepLoading(false)
      })

    return () => {
      ignore = true
    }
  }, [activeSolveId])

  // Debounced search / initial load
  useEffect(() => {
    if (demo) return

    const timer = setTimeout(() => {
      setLoading(true)
      getSolves(null, searchTerm.trim() || null)
        .then((res) => {
          setItems(res.items)
          setNextCursor(res.next)
        })
        .catch(() => {
          setItems([])
          setNextCursor(null)
        })
        .finally(() => setLoading(false))
    }, 300)

    return () => clearTimeout(timer)
  }, [searchTerm])

  const loadMore = async () => {
    if (!nextCursor || loading) return
    setLoading(true)
    try {
      const res = await getSolves(nextCursor, searchTerm.trim() || null)
      setItems((prev) => [...prev, ...res.items])
      setNextCursor(res.next)
    } finally {
      setLoading(false)
    }
  }

  if (demo) {
    return (
      <main className={wrap}>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="mt-4 text-muted-foreground">History needs sign-in</p>
      </main>
    )
  }

  // Detail view for #history/<id>
  if (activeSolveId) {
    return (
      <main className={wrap}>
        <div className="mb-4">
          <a href="#history" className="text-sm font-medium text-primary hover:underline">
            &larr; Back to History
          </a>
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">Solve Details</h1>

        {stepLoading && <p className="mt-4 text-sm text-muted-foreground">Loading solve…</p>}

        {stepError && (
          <p role="alert" className="mt-4 text-sm font-medium text-destructive">
            {stepError}
          </p>
        )}

        {activeStep && activeStep.type === 'final' && (
          <Suspense fallback={<p className="mt-6 text-sm text-muted-foreground">Loading answer…</p>}>
            <AnswerCard a={activeStep} />
          </Suspense>
        )}

        {activeStep && activeStep.type !== 'final' && (
          <div className="mt-4 rounded-lg border bg-card p-4">
            <p className="text-sm text-muted-foreground">This solve did not finish.</p>
          </div>
        )}
      </main>
    )
  }

  const groups = groupSolves(items)

  return (
    <main className={wrap}>
      <h1 className="text-2xl font-semibold tracking-tight">History</h1>

      <div className="mt-4">
        <input
          type="search"
          placeholder="Search questions…"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
          maxLength={80}
        />
      </div>

      <div className="mt-6 space-y-6">
        {renderGroup('Today', groups.today)}
        {renderGroup('Yesterday', groups.yesterday)}
        {renderGroup('Last 7 days', groups.last7Days)}
        {renderGroup('Older', groups.older)}

        {items.length === 0 && !loading && (
          <p className="text-sm text-muted-foreground">No solves found.</p>
        )}

        {nextCursor && (
          <div className="pt-2">
            <Button variant="outline" onClick={loadMore} disabled={loading}>
              {loading ? 'Loading…' : 'Load more'}
            </Button>
          </div>
        )}
      </div>
    </main>
  )
}

function renderGroup(title: string, list: SolveItem[]) {
  if (!list.length) return null
  return (
    <section>
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      <ul className="mt-2 divide-y rounded-lg border bg-card">
        {list.map((item) => (
          <li key={item.id} className="p-3 text-sm hover:bg-muted/50">
            <a href={`#history/${item.id}`} className="block">
              <p className="font-medium text-foreground">{item.question || 'Untitled question'}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Status: {item.status}{item.updated_at ? ` · ${new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
              </p>
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}

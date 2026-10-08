import * as mock from './mock'
import type { Dashboard, ResultBody, SolveStart, Step } from './types'

const BASE = import.meta.env.VITE_API_URL as string | undefined

// ponytail: no retry — retrying POST /solve could create duplicate solves
async function post<T>(path: string, body: unknown, onSlow?: () => void): Promise<T> {
  const t = setTimeout(() => onSlow?.(), 3000) // Render free tier sleeps
  try {
    const r = await fetch(`${BASE}/api/v1${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

export const startSolve = (question: string, onSlow?: () => void): Promise<SolveStart> =>
  BASE ? post('/solve', { question }, onSlow) : mock.startSolve(question)

export const postResult = async (id: string, body: ResultBody, onSlow?: () => void): Promise<Step> =>
  BASE ? (await post<{ step: Step }>(`/solve/${id}/result`, body, onSlow)).step : mock.postResult(id, body)

export async function getDashboard(): Promise<Dashboard> {
  if (!BASE) return mock.getDashboard()
  const r = await fetch(`${BASE}/api/v1/dashboard`)
  if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
  return (await r.json()) as Dashboard
}

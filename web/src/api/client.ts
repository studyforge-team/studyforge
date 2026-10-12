import { supabase } from '@/lib/supabase'
import * as mock from './mock'
import type { Dashboard, Quiz, ResultBody, SolveStart, Step, UploadKind, UploadRead } from './types'

const BASE = import.meta.env.VITE_API_URL as string | undefined

// Bearer token for the backend (AU1 verifies it). Never passed to the Pyodide worker.
const auth = async (): Promise<Record<string, string>> => {
  const t = (await supabase?.auth.getSession())?.data.session?.access_token
  return t ? { Authorization: `Bearer ${t}` } : {}
}

// ponytail: no retry — retrying POST /solve could create duplicate solves
async function post<T>(path: string, body: unknown | FormData, onSlow?: () => void): Promise<T> {
  const t = setTimeout(() => onSlow?.(), 3000) // Render free tier sleeps
  try {
    const r = await fetch(`${BASE}/api/v1${path}`, {
      method: 'POST',
      // FormData: the browser sets the multipart Content-Type (with boundary) itself
      ...(body instanceof FormData ? { body, headers: await auth() } : { headers: { 'Content-Type': 'application/json', ...(await auth()) }, body: JSON.stringify(body) }),
    })
    if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

export const startSolve = (question: string, onSlow?: () => void, uploadId?: string): Promise<SolveStart> =>
  BASE ? post('/solve', uploadId ? { question, upload_id: uploadId } : { question }, onSlow) : mock.startSolve(question)

export function uploadFile(file: File, kind: UploadKind, onSlow?: () => void): Promise<{ upload_id: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('kind', kind)
  return BASE ? post('/uploads', form, onSlow) : mock.uploadFile()
}

export const readUpload = (id: string, onSlow?: () => void): Promise<UploadRead> =>
  BASE ? post(`/uploads/${id}/read`, {}, onSlow) : mock.readUpload()

export const postResult = async (id: string, body: ResultBody, onSlow?: () => void): Promise<Step> =>
  BASE ? (await post<{ step: Step }>(`/solve/${id}/result`, body, onSlow)).step : mock.postResult(id, body)

export async function getDashboard(): Promise<Dashboard> {
  if (!BASE) return mock.getDashboard()
  const r = await fetch(`${BASE}/api/v1/dashboard`, { headers: await auth() })
  if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
  return (await r.json()) as Dashboard
}

// POST /api/v1/quizzes {topic|upload_id} -> quiz (§3.5). Response `id` is a gap.
export const getQuiz = (topic: string, onSlow?: () => void): Promise<Quiz> =>
  BASE ? post('/quizzes', { topic }, onSlow) : mock.getQuiz()

// Fire-and-forget; failures are swallowed (a missed report or save must never block the student).
const quiet = (path: string, body: unknown) => { void post(path, body).catch(() => {}) }

// P1 request #8, endpoint not built yet. Body shape is a gap. No-op in demo or without a quiz id.
export const reportItem = (quizId: string | undefined, index: number, reason: string) => {
  if (BASE && quizId) quiet(`/quizzes/${quizId}/report`, { index, reason })
}

// Not in the contract; body shape is a gap. Demo mode saves to localStorage in the page instead.
export const saveAnswers = (quizId: string | undefined, answers: string[], score: number) => {
  if (BASE && quizId) quiet(`/quizzes/${quizId}/answers`, { answers, score })
}

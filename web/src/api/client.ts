import * as mock from './mock'
import type { Dashboard, Quiz, QuizAttemptsResponse, QuizOpts, ResultBody, SolveStart, SolvesResponse, Step, UploadKind, UploadRead } from './types'

const BASE = import.meta.env.VITE_API_URL as string | undefined

// ponytail: no retry — retrying POST /solve could create duplicate solves
async function post<T>(path: string, body: unknown | FormData, onSlow?: () => void): Promise<T> {
  const t = setTimeout(() => onSlow?.(), 3000) // Render free tier sleeps
  try {
    const r = await fetch(`${BASE}/api/v1${path}`, {
      method: 'POST',
      // FormData: the browser sets the multipart Content-Type (with boundary) itself
      ...(body instanceof FormData ? { body } : { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
    })
    if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

async function get<T>(path: string, onSlow?: () => void): Promise<T> {
  const t = setTimeout(() => onSlow?.(), 3000)
  try {
    const r = await fetch(`${BASE}/api/v1${path}`)
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
  const r = await fetch(`${BASE}/api/v1/dashboard`)
  if (!r.ok) throw new Error(`Server error (HTTP ${r.status})`)
  return (await r.json()) as Dashboard
}

// T1/T3: getQuiz accepts a topic string (backward compat) or a full QuizOpts object.
export function getQuiz(opts: string | QuizOpts, onSlow?: () => void): Promise<Quiz> {
  const body: QuizOpts = typeof opts === 'string' ? { topic: opts } : opts
  if (!BASE) return mock.getQuiz(body)
  return post<Quiz>('/quizzes', body, onSlow)
}

export function saveAnswers(
  quizId: string,
  answers: (number | string | null)[],
  score: number,
  correct: (boolean | null)[],
): Promise<{ recorded: number }> {
  if (!BASE) return Promise.resolve({ recorded: 0 })
  return post(`/quizzes/${quizId}/answers`, { answers, score, correct })
}

// T4: per-topic quiz attempt history
export async function getQuizAttempts(): Promise<QuizAttemptsResponse> {
  if (!BASE) return { topics: [] }
  return get<QuizAttemptsResponse>('/quiz-attempts')
}

// T5: paginated solve history
export async function getSolves(
  before?: string | null,
  q?: string | null,
  onSlow?: () => void,
): Promise<SolvesResponse> {
  if (!BASE) return { items: [], next: null }
  const params = new URLSearchParams()
  if (before) params.set('before', before)
  if (q) params.set('q', q)
  const qs = params.toString() ? `?${params.toString()}` : ''
  return get<SolvesResponse>(`/solves${qs}`, onSlow)
}

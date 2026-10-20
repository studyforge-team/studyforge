import { supabase } from '@/lib/supabase'
import { HttpError, PlainError } from '@/lib/errors'
import * as mock from './mock'
import type { CheckinResult, Dashboard, Notice, NoticeIn, PdfRead, PrepPack, Quiz, QuizAttempts, QuizRequest, ResultBody, SolveStart, Step, UploadKind, UploadRead } from './types'

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
      signal: AbortSignal.timeout(90_000), // model timeout; friendly() words it
      // FormData: the browser sets the multipart Content-Type (with boundary) itself
      ...(body instanceof FormData ? { body, headers: await auth() } : { headers: { 'Content-Type': 'application/json', ...(await auth()) }, body: JSON.stringify(body) }),
    })
    if (!r.ok) throw new HttpError(r.status)
    return (await r.json()) as T
  } finally {
    clearTimeout(t)
  }
}

// confirmed: true = the student approved this text on the confirm screen (server then skips need_confirm)
export const startSolve = (question: string, onSlow?: () => void, uploadId?: string, confirmed?: boolean): Promise<SolveStart> =>
  BASE ? post('/solve', { question, ...(uploadId && { upload_id: uploadId }), ...(confirmed && { confirmed: true }) }, onSlow) : mock.startSolve(question)

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
  const r = await fetch(`${BASE}/api/v1/dashboard`, { headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok) throw new HttpError(r.status)
  return (await r.json()) as Dashboard
}

// POST /api/v1/quizzes {topic, n_items, kinds, marks_per_q, upload_id?} -> quiz (§3.5). A string is just the topic.
export const getQuiz = (opts: string | QuizRequest, onSlow?: () => void): Promise<Quiz> => {
  const body = typeof opts === 'string' ? { topic: opts } : opts
  return BASE ? post('/quizzes', body, onSlow) : mock.getQuiz(body)
}

// T4: GET /quiz-attempts. Demo mode has no account, so no history. A 401 (signed out) is for the page to hide.
export async function getQuizAttempts(): Promise<QuizAttempts> {
  if (!BASE) return { topics: [] }
  const r = await fetch(`${BASE}/api/v1/quiz-attempts`, { headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok) throw new HttpError(r.status)
  return (await r.json()) as QuizAttempts
}

// D7: POST /checkins/{job_id}. 409 = already answered, 404 = gone (HttpError.status).
export const answerCheckin = (jobId: string, correct: boolean): Promise<CheckinResult> =>
  BASE ? post(`/checkins/${encodeURIComponent(jobId)}`, { correct }) : mock.answerCheckin(correct)

// Fire-and-forget; failures are swallowed (a missed report or save must never block the student).
const quiet = (path: string, body: unknown) => { void post(path, body).catch(() => {}) }

// P1 request #8, endpoint not built yet. Body shape is a gap. No-op in demo or without a quiz id.
export const reportItem = (quizId: string | undefined, index: number, reason: string) => {
  if (BASE && quizId) quiet(`/quizzes/${quizId}/report`, { index, reason })
}

// Not in the contract; body shape is a gap. Demo mode saves to localStorage in the page instead.
export const saveAnswers = (quizId: string | undefined, answers: string[], score: number, correct: (boolean | null)[]) => {
  if (BASE && quizId) quiet(`/quizzes/${quizId}/answers`, { answers, score, correct })
}

// D10 privacy panel. No demo fallback: there is no account to export or delete.
async function me<T>(method: 'GET' | 'DELETE', read: (r: Response) => Promise<T>): Promise<T> {
  if (!BASE) throw new PlainError('Account tools need the live backend.')
  const r = await fetch(`${BASE}/api/v1/me${method === 'GET' ? '/export' : ''}`, { method, headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok) throw new HttpError(r.status)
  return read(r)
}
export const exportMyData = (): Promise<Blob> => me('GET', (r) => r.blob())
export const deleteAccount = (): Promise<void> => me('DELETE', async () => {})

// Notices (D1). Demo mode keeps them in this browser (mock.ts).
export const addNotice = (n: NoticeIn): Promise<Notice> => (BASE ? post('/notices', n) : mock.addNotice(n)) // 201

export async function listNotices(): Promise<Notice[]> {
  if (!BASE) return mock.listNotices()
  const r = await fetch(`${BASE}/api/v1/notices`, { headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok) throw new HttpError(r.status)
  return ((await r.json()) as { notices: Notice[] }).notices
}

export async function deleteNotice(id: string): Promise<void> {
  if (!BASE) return mock.deleteNotice(id)
  const r = await fetch(`${BASE}/api/v1/notices/${encodeURIComponent(id)}`, { method: 'DELETE', headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok && r.status !== 404) throw new HttpError(r.status) // 404: already gone
}

// Phone reminders (D1b), docs/api-contract.md §5. Live backend only: demo mode has no account to remind.
async function pushApi<T>(method: 'GET' | 'POST' | 'DELETE', path: string, body?: unknown): Promise<T> {
  if (!BASE) throw new PlainError('Phone reminders need the live app.')
  const r = await fetch(`${BASE}/api/v1/push${path}`, {
    method, signal: AbortSignal.timeout(90_000),
    headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(await auth()) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!r.ok && !(method === 'DELETE' && r.status === 404)) throw new HttpError(r.status) // 404 on delete: already off
  return (r.status === 204 || method === 'DELETE' ? undefined : await r.json()) as T
}
export const getPushKey = async (): Promise<string> => (await pushApi<{ public_key: string }>('GET', '/key')).public_key
export const savePushSubscription = (sub: PushSubscriptionJSON): Promise<void> => pushApi('POST', '/subscriptions', sub)
export const deletePushSubscription = (endpoint: string): Promise<void> => pushApi('DELETE', `/subscriptions?endpoint=${encodeURIComponent(endpoint)}`)
export const sendTestPush = async (): Promise<number> => (await pushApi<{ sent: number }>('POST', '/test')).sent

// D5: GET /prep/{key}, built by the server the first time it is opened (needs the model then).
export async function getPrep(key: string, onSlow?: () => void): Promise<PrepPack> {
  if (!BASE) return mock.getPrep()
  const t = setTimeout(() => onSlow?.(), 3000) // Render free tier sleeps; building can also take a while
  try {
    const r = await fetch(`${BASE}/api/v1/prep/${encodeURIComponent(key)}`, { headers: await auth(), signal: AbortSignal.timeout(90_000) })
    if (!r.ok) throw new HttpError(r.status)
    return (await r.json()) as PrepPack
  } finally {
    clearTimeout(t)
  }
}

// C1: a signed link to one of the student's own uploads, valid 10 minutes.
export async function getUploadUrl(id: string): Promise<string> {
  if (!BASE) throw new PlainError('Your notes open in the live app.')
  const r = await fetch(`${BASE}/api/v1/uploads/${encodeURIComponent(id)}`, { headers: await auth(), signal: AbortSignal.timeout(90_000) })
  if (!r.ok) throw new HttpError(r.status)
  return ((await r.json()) as { url: string }).url
}

// PY/TE: page count, words and text of a PDF the student picks. Read on the server and not stored.
export async function readPdf(file: File, onSlow?: () => void): Promise<PdfRead> {
  if (!BASE) throw new PlainError('Reading a PDF works in the live app once you sign in.')
  if (file.size > 10 * 1024 * 1024) throw new PlainError('That PDF is over 10 MB.')
  const form = new FormData()
  form.append('file', file)
  return post('/pdf/read', form, onSlow)
}

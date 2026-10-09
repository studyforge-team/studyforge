import * as mock from './mock'
import type { Dashboard, ResultBody, SolveStart, Step, UploadKind, UploadRead } from './types'

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

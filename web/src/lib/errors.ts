// Pure on purpose (no '@/' imports, no React) so `node --test` can load it.
export class HttpError extends Error {
  status: number
  constructor(status: number) { super(`HTTP ${status}`); this.status = status }
}
// Thrown by app code; its message is already plain English and is shown as is.
export class PlainError extends Error {}

// One plain sentence per failure. Never returns e.message of unknown errors (stack traces / internals).
export function friendly(e: unknown): string {
  if (e instanceof PlainError) return e.message
  if (e instanceof HttpError) {
    const s = e.status
    if (s === 401) return 'Your session ended. Sign in again.'
    if (s === 404) return 'That question or session no longer exists. Start again.'
    if (s === 409) return "You've reached the 20-file upload limit. Free space under Your data (Settings → Your data)."
    if (s === 413) return 'That result was too large for the server.'
    if (s === 415) return "That file type isn't supported. Upload a PDF or an image."
    if (s === 422) return "The app sent something the server didn't understand. Reload the page."
    if (s === 429) return "You've hit today's limit. Try again tomorrow."
    if (s >= 500) return 'The server is having trouble. Try again in a minute.'
  }
  const name = (e as { name?: string } | null)?.name
  if (name === 'TimeoutError' || name === 'AbortError') return 'The server took too long to answer. Try again.'
  if (e instanceof TypeError) return "Can't reach the server. Check your connection."
  return 'Something went wrong. Try again.'
}

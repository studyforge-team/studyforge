// Web Share Target (D1). Once StudyForge is installed (Android Chrome/Edge: menu > Install app), it
// appears in the phone's Share menu; the manifest sends what was shared to
// /?share_title=…&share_text=…&share_url=… . Pure apart from captureShare (no '@/' imports, no React).
export type Shared = { title: string; text: string; url: string }

export const SHARE_PARAMS = { title: 'share_title', text: 'share_text', url: 'share_url' } as const // = manifest.webmanifest
export const MAX_TEXT = 5000 // = api/app/routers/notices.py MAX_TEXT
export const MAX_TITLE = 200
export const MAX_URL = 2000

// The shared fields (null when nothing was shared) and the query string without them: other
// parameters, such as the ?code= of a sign-in return, are kept.
export function readShare(search: string): { shared: Shared | null; rest: string } {
  const q = new URLSearchParams(search)
  const s = { title: '', text: '', url: '' }
  for (const [k, p] of Object.entries(SHARE_PARAMS) as [keyof Shared, string][]) {
    s[k] = (q.get(p) ?? '').trim()
    q.delete(p)
  }
  const rest = q.toString()
  return { shared: s.title || s.text || s.url ? s : null, rest: rest ? `?${rest}` : '' }
}

// Lone surrogate halves (e.g. an emoji cut in two at a length limit) cannot be stored: drop them.
export function wellFormed(t: string): string {
  let out = '' // a plain loop: regex lookbehind would break the whole app on Safari before 16.4
  for (let i = 0; i < t.length; i++) {
    const c = t.charCodeAt(i)
    if (c >= 0xd800 && c <= 0xdbff) {
      const d = t.charCodeAt(i + 1)
      if (d >= 0xdc00 && d <= 0xdfff) { out += t[i] + t[i + 1]; i++ }
    } else if (c < 0xdc00 || c > 0xdfff) out += t[i]
  }
  return out
}

export const isHttpUrl = (u: string): boolean => {
  // nothing hidden in a link: no spaces, control, format (e.g. zero-width) or unassigned characters;
  // the same rule as the server's str.isprintable() plus its no-whitespace check
  // ^https?:// as written: new URL() would also accept 'http:example.com', which the server refuses
  if (!u || u.length > MAX_URL || !/^https?:\/\//i.test(u) || /[\p{C}\p{Z}]/u.test(u)) return false
  try {
    const x = new URL(u)
    return (x.protocol === 'https:' || x.protocol === 'http:') && x.hostname !== ''
  } catch {
    return false
  }
}

// What goes in the paste box: the shared text, plus the link when the text does not already contain
// it; the title only when there is nothing else. Cut to the server's limit (the page says so).
export function draftFrom(s: Shared): { draft: string; cut: boolean } {
  const body = [s.text, s.url && !s.text.includes(s.url) ? s.url : ''].filter(Boolean).join('\n') || s.title
  return { draft: wellFormed(body.slice(0, MAX_TEXT)), cut: body.length > MAX_TEXT }
}

// The shared fields survive a reload in this tab (signing in with Google leaves the page and comes
// back) until the notice is saved or discarded. Storage can be blocked: then memory only.
const KEY = 'studyforge.share.v1'
const REOPEN_MS = 10 * 60_000 // a sign-in return reopens Notices only this soon after the share
let pending: Shared | null = null

// Called once before the app renders: keeps the shared fields and takes them out of the address bar
// and the history entry, then opens the Notices page.
export function captureShare(): void {
  const { shared, rest } = readShare(location.search)
  if (!shared) {
    // back from signing in (?code=) with a shared notice still unsaved: reopen it
    if (!location.hash && new URLSearchParams(location.search).has('code') && getShare() && Date.now() - sharedAt() < REOPEN_MS) history.replaceState(null, '', `${location.pathname}${location.search}#notices`)
    return
  }
  pending = shared
  try { sessionStorage.setItem(KEY, JSON.stringify({ ...shared, at: Date.now() })) } catch { /* memory only */ }
  history.replaceState(null, '', `${location.pathname}${rest}#notices`)
}

export function getShare(): Shared | null {
  if (pending) return pending
  try {
    const v: unknown = JSON.parse(sessionStorage.getItem(KEY) ?? 'null')
    const o = v as Record<string, unknown> | null
    if (o && typeof o.title === 'string' && typeof o.text === 'string' && typeof o.url === 'string') pending = { title: o.title, text: o.text, url: o.url }
  } catch { /* nothing kept */ }
  return pending
}

function sharedAt(): number {
  try { return Number((JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as { at?: unknown }).at) || 0 } catch { return 0 }
}

export function clearShare(): void {
  pending = null
  try { sessionStorage.removeItem(KEY) } catch { /* memory only */ }
}

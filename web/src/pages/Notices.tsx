import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { addNotice, deleteNotice, listNotices } from '@/api/client'
import type { Notice } from '@/api/types'
import { HttpError, friendly } from '@/lib/errors'
import { clearShare, draftFrom, getShare, isHttpUrl, MAX_TEXT, MAX_TITLE, wellFormed } from '@/lib/share'
import { supabase } from '@/lib/supabase'
import { useSlow } from '@/lib/useSlow'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts
const field = 'mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-base'
const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
// Notice-specific wording: the generic 422/413 text says "reload", which would lose the draft.
const why = (e: unknown) => {
  const s = e instanceof HttpError ? e.status : 0
  if (s === 503) return "Notices aren't switched on on the server yet."
  if (s === 429) return 'You have 500 notices, the most StudyForge keeps. Delete some to save new ones.'
  if (s === 422 || s === 413) return 'The server did not accept this notice. Shorten it or remove the link, then save again.'
  return friendly(e)
}

// D1: paste a notice, or share one here from another app (lib/share.ts). Notices are only kept for
// now; turning them into tasks and reminders is a later ticket.
export default function Notices() {
  const [shared, setShared] = useState(getShare)
  const [draft, setDraft] = useState(() => (shared ? draftFrom(shared).draft : ''))
  // whose list is on screen: 'demo', a user id, or null (signed out). The list is kept with its
  // owner, so a token refresh or tab refocus (same user) keeps it, and another account never sees it.
  const [owner, setOwner] = useState<string | null>(demo ? 'demo' : null)
  const [list, setList] = useState<{ owner: string; items: Notice[] } | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  const listHead = useRef<HTMLHeadingElement>(null)
  const ownerNow = useRef(owner)
  const [tries, setTries] = useState(0)
  const [loadFailed, setLoadFailed] = useState(false)
  const cut = !!shared && draftFrom(shared).cut
  const items = list && list.owner === owner ? list.items : null
  const slow = useSlow(!!owner && items === null && !loadFailed)

  useEffect(() => {
    if (demo || !supabase) return
    // INITIAL_SESSION arrives first on subscribe, so no getSession() that could land after a newer event
    const { data } = supabase.auth.onAuthStateChange((_e, s) => {
      const id = s?.user.id ?? null
      if (id !== ownerNow.current) setErr('') // the last account's error is not this one's
      ownerNow.current = id
      setOwner(id)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!owner) return
    let live = true
    listNotices().then((n) => { if (live) { setList({ owner, items: n }); setLoadFailed(false) } }, (e: unknown) => { if (live) { setErr(why(e)); setLoadFailed(true) } })
    return () => { live = false }
  }, [owner, tries])

  const discard = () => { clearShare(); setShared(null); setDraft(''); box.current?.focus() }

  const save = async () => {
    const text = wellFormed(draft).trim()
    if (!text || busy || !owner) return // busy: a double tap must not save twice
    setBusy(true); setErr(''); setMsg('')
    try {
      const url = shared && isHttpUrl(shared.url) ? shared.url : undefined
      const title = shared?.title ? wellFormed(shared.title.slice(0, MAX_TITLE)).trim() : undefined
      const base = { text, source: shared ? ('share' as const) : ('paste' as const), ...(title && { title }) }
      // the link is also in the text, so if the server refuses only the link, save without it
      const n = await addNotice(url ? { ...base, url } : base).catch((e: unknown) => {
        if (url && e instanceof HttpError && e.status === 422) return addNotice(base)
        throw e
      })
      setList((l) => ({ owner, items: [n, ...(l && l.owner === owner ? l.items : [])] }))
      setDraft((d) => (wellFormed(d).trim() === text ? '' : d)) // keep anything typed while saving
      clearShare(); setShared(null); setMsg('Notice saved.')
    } catch (e) {
      setErr(why(e))
    } finally {
      setBusy(false)
      box.current?.focus() // the disabled button would otherwise drop focus to the page
    }
  }

  const remove = async (n: Notice) => {
    setErr(''); setMsg('')
    try {
      await deleteNotice(n.id)
      setList((l) => (l && l.owner === owner ? { owner, items: l.items.filter((x) => x.id !== n.id) } : l))
      setMsg('Notice deleted.')
      listHead.current?.focus() // the focused Delete button is gone
    } catch (e) {
      setErr(why(e))
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Notices</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Keep notices here: a class WhatsApp message, an email about a deadline. Paste one below. On Android you can
        also install StudyForge (browser menu, then Install app) and share a message straight to it. Notices are only
        kept for now; turning them into tasks and reminders comes later.
      </p>

      <section className="mt-5 rounded-lg border bg-card p-4 sm:p-5">
        {shared && <p className="text-sm font-medium">Shared to StudyForge{shared.title ? ` from “${shared.title.slice(0, MAX_TITLE)}”` : ''}. Check it, then save.</p>}
        {cut && <p className="mt-1 text-sm text-warn">The shared text was longer than {MAX_TEXT} characters and was cut.</p>}
        <label htmlFor="notice" className="mt-2 block text-sm font-medium">Notice</label>
        <textarea id="notice" ref={box} rows={6} maxLength={MAX_TEXT} className={field} value={draft} autoFocus={!!shared}
          placeholder="CRE assignment 3 due Friday 5 pm, submit on the portal." aria-describedby="notice-count"
          onChange={(e) => { setDraft(e.target.value); setMsg('') }} />
        <div id="notice-count" className="mt-1 text-right text-xs text-muted-foreground">{draft.length} / {MAX_TEXT}</div>
        {!owner && <p className="mt-2 text-sm text-muted-foreground">Sign in to save notices.</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <Button className="min-h-11" disabled={!owner || busy || !draft.trim()} onClick={() => void save()}>{busy ? 'Saving…' : 'Save notice'}</Button>
          {shared && <Button variant="outline" className="min-h-11" onClick={discard}>Discard shared text</Button>}
        </div>
        <p role="status" className="mt-2 text-sm text-primary empty:hidden">{msg}</p>
        {err && <p role="alert" className="mt-2 text-sm text-destructive">{err}</p>}
        {demo && <p className="mt-2 text-xs text-muted-foreground">Demo mode: notices stay in this browser.</p>}
      </section>

      {owner && (
        <section className="mt-5" aria-labelledby="saved">
          <h2 id="saved" ref={listHead} tabIndex={-1} className="text-base font-semibold">Saved notices</h2>
          {items === null ? (
            loadFailed
              ? <Button variant="outline" className="mt-2 min-h-11" onClick={() => { setErr(''); setLoadFailed(false); setTries((t) => t + 1) }}>Try again</Button>
              : <><p className="mt-2 text-sm text-muted-foreground">Loading…</p>{slow && <p className="mt-1 text-sm text-muted-foreground">Waking up the server…</p>}</>
          ) : items.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No notices yet.</p>
          ) : (
            <ul className="mt-2 space-y-3">
              {items.map((n) => (
                <li key={n.id} className="rounded-lg border bg-card p-4">
                  <p className="text-xs text-muted-foreground">{when(n.created_at)} · {n.source === 'share' ? 'Shared' : 'Pasted'}{n.title ? ` · ${n.title}` : ''}</p>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm">{n.text}</p>
                  {n.url && isHttpUrl(n.url) && (
                    <a href={n.url} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 inline-flex min-h-11 items-center break-all text-sm text-primary underline">{n.url}</a>
                  )}
                  <div><Button variant="outline" className="mt-2 min-h-11" aria-label={`Delete notice: ${n.text.slice(0, 60)}`} onClick={() => void remove(n)}>Delete</Button></div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}

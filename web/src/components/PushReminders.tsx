import { useEffect, useRef, useState } from 'react'
import { sendTestPush } from '@/api/client'
import { Button } from '@/components/ui/button'
import { HttpError, friendly } from '@/lib/errors'
import { prepare, pushIsOn, pushSupported, turnOff, turnOn } from '@/lib/pushReminders'
import { supabase } from '@/lib/supabase'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts
const why = (e: unknown, tooMany: string) => {
  const s = e instanceof HttpError ? e.status : 0
  if (s === 503) return 'Phone reminders aren’t switched on on the server yet.'
  if (s === 429) return tooMany
  return friendly(e)
}

// D1b: "Turn on phone reminders" on Today. The same reminders still appear in the inbox below.
export default function PushReminders() {
  const [signedIn, setSignedIn] = useState(false)
  const [on, setOn] = useState(false)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const status = useRef<HTMLParagraphElement>(null)
  const ready = useRef<ReturnType<typeof prepare> | null>(null)

  useEffect(() => {
    if (demo || !supabase) return
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSignedIn(!!s))
    return () => data.subscription.unsubscribe()
  }, [])
  useEffect(() => {
    if (!signedIn || !pushSupported()) return
    let live = true
    pushIsOn().then((v) => live && setOn(v), () => {})
    // fetch the key and register the worker now, so the tap only asks permission and subscribes (iOS)
    ready.current = prepare()
    ready.current.catch(() => { ready.current = null }) // retried on the tap, with its error shown then
    return () => { live = false }
  }, [signedIn])

  const run = async (job: () => Promise<string>, tooMany: string) => {
    setBusy(true); setErr(''); setMsg('')
    try { setMsg(await job()) } catch (e) { setErr(why(e, tooMany)) } finally {
      setBusy(false)
      status.current?.focus() // the pressed button is replaced or disabled: keep focus on the result
    }
  }
  const DEVICES = 'Reminders are on for 10 devices already. Turn them off on one you no longer use.'
  const TESTS = 'You’ve sent 3 tests in the last 10 minutes. Try again later.'

  let note = ''
  if (demo) note = 'Phone reminders work in the live app once you sign in.'
  else if (!pushSupported()) note = 'This browser can’t show phone reminders. On iPhone, tap Share, then Add to Home Screen, and open StudyForge from there (iOS 16.4 or later).'
  else if (!signedIn) note = 'Sign in to turn on phone reminders.'

  return (
    <div className="mb-3 rounded-lg border bg-card p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Phone reminders</h2>
      {note ? <p className="mt-2 text-sm text-muted-foreground">{note}</p> : (
        <>
          <p className="mt-2 text-sm">{on ? 'On for this device: 3 days before, 1 day before and on the morning of each deadline.' : 'Get a notification on this device before each deadline, even with StudyForge closed.'}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {on ? (
              <>
                <Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void run(async () => { const n = await sendTestPush(); return n ? 'Test sent. It should arrive in a few seconds.' : 'No device took the test. Turn reminders off and on again.' }, TESTS)}>Send a test</Button>
                <Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void run(async () => { await turnOff(); setOn(false); return 'Phone reminders are off for this device.' }, DEVICES)}>Turn off</Button>
              </>
            ) : (
              <Button className="min-h-11" disabled={busy} onClick={() => void run(async () => { await turnOn(ready.current ?? undefined); setOn(true); return 'Phone reminders are on for this device.' }, DEVICES)}>{busy ? 'Turning on…' : 'Turn on phone reminders'}</Button>
            )}
          </div>
        </>
      )}
      {/* always rendered, so screen readers announce changes; focused after each action */}
      <p ref={status} role="status" tabIndex={-1} className={msg || err ? 'mt-2 text-sm outline-none' : 'sr-only'}>
        {err ? <span className="text-destructive">{err}</span> : <span className="text-primary">{msg}</span>}
      </p>
    </div>
  )
}

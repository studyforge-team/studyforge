import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { Button } from '@/components/ui/button'
import { turnOff } from '@/lib/pushReminders' // D1b: stop this device's reminders while the token still works
import { getCaptchaToken, supabase } from '@/lib/supabase'

export default function Auth() {
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!supabase) return
    void supabase.auth.getSession().then(({ data }) => setSession(data.session))
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])
  if (!supabase) return null
  const run = async (p: Promise<{ error: { message: string } | null }>) => setError((await p.catch((e: Error) => ({ error: e }))).error?.message ?? '')
  return (
    <div className="border-b bg-card print:hidden">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-2 px-4 py-2">
        {session ? (
          <>
            <span className="min-w-0 flex-1 truncate text-sm">{session.user.is_anonymous ? 'Demo student' : session.user.email}</span>
            <Button variant="outline" onClick={() => void run(turnOff().catch(() => {}).then(() => supabase!.auth.signOut()))}>Sign out</Button>
          </>
        ) : (
          <>
            <Button onClick={() => void run(supabase!.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: location.origin } }))}>Sign in with Google</Button>
            <Button variant="outline" onClick={() => void run(supabase!.auth.signInAnonymously({ options: { captchaToken: getCaptchaToken() } }))}>Try demo</Button>
          </>
        )}
        {error && <p role="alert" className="w-full text-sm text-destructive">{error}</p>}
      </div>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { deleteAccount, exportMyData } from '@/api/client'
import { HttpError, friendly } from '@/lib/errors'
import { supabase } from '@/lib/supabase'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts

export default function Privacy() {
  const [signedIn, setSignedIn] = useState(false)
  const [confirm, setConfirm] = useState('')
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    if (!supabase) return
    void supabase.auth.getSession().then(({ data }) => setSignedIn(!!data.session))
    const { data } = supabase.auth.onAuthStateChange((_e, s) => setSignedIn(!!s))
    return () => data.subscription.unsubscribe()
  }, [])
  const off = demo || !signedIn
  const run = async (job: () => Promise<void>) => {
    setBusy(true); setErr(''); setMsg('')
    try { await job() } catch (e) { setErr(e instanceof HttpError && e.status === 503 ? "Account tools aren't switched on yet." : friendly(e)) } finally { setBusy(false) }
  }
  const download = () => run(async () => {
    const a = document.createElement('a')
    a.href = URL.createObjectURL(await exportMyData())
    a.download = 'studyforge-export.json'
    a.click()
    URL.revokeObjectURL(a.href)
  })
  const remove = () => run(async () => {
    await deleteAccount()
    setConfirm('')
    setMsg('Your account and data are deleted.')
    await supabase?.auth.signOut()
  })
  return (
    <main className="mx-auto max-w-3xl px-4 py-6">
      <h1 className="text-xl font-semibold">Your data</h1>
      {off && <p className="mt-2 text-sm text-muted-foreground">Sign in to download or delete your data.</p>}
      <section aria-label="Download" className="mt-4 space-y-2">
        <p className="text-sm">Get everything we store about you (solves, quizzes, model calls) as a JSON file.</p>
        <Button disabled={off || busy} onClick={() => void download()}>Download my data</Button>
      </section>
      <section aria-label="Delete" className="mt-6 space-y-2">
        <p className="text-sm">Deleting removes your solves, quizzes and sign-in account for good. Model-call cost records stay, with your id removed.</p>
        <label className="block text-sm" htmlFor="confirm-delete">Type DELETE to confirm</label>
        <input id="confirm-delete" className="block h-11 w-full max-w-xs rounded-lg border bg-background px-3 text-sm" value={confirm} disabled={off || busy} autoComplete="off" onChange={(e) => setConfirm(e.target.value)} />
        <Button variant="destructive" disabled={off || busy || confirm !== 'DELETE'} onClick={() => void remove()}>Delete my account</Button>
      </section>
      {msg && <p role="status" className="mt-4 text-sm font-medium">{msg}</p>}
      {err && <p role="alert" className="mt-4 text-sm font-medium text-destructive">{err}</p>}
    </main>
  )
}

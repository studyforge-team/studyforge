import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { signOut, useSession } from '@/components/Auth'
import { getTheme, setTheme, type Theme } from '@/lib/theme'

const themes: [Theme, string][] = [['light', 'Light'], ['dark', 'Dark'], ['system', 'System']]
const row = 'flex min-h-11 items-center text-sm font-medium text-primary hover:underline'

export default function Settings() {
  const [theme, set] = useState(getTheme())
  const session = useSession()
  return (
    <main className="sf-in mx-auto max-w-3xl space-y-6 px-4 py-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
      <fieldset className="rounded-lg border bg-card p-4">
        <legend className="px-1 text-sm font-semibold">Appearance</legend>
        <div className="flex flex-wrap gap-x-6">
          {themes.map(([v, label]) => (
            <label key={v} className="flex min-h-11 items-center gap-2 text-sm">
              <input type="radio" name="theme" className="size-4 accent-primary" checked={theme === v} onChange={() => { setTheme(v); set(v) }} />{label}
            </label>
          ))}
        </div>
      </fieldset>
      <section aria-label="More" className="rounded-lg border bg-card px-4 py-1">
        <a href="#" className={row}>Phone reminders (on Today)</a>
        <a href="#privacy" className={row}>Your data: export or delete</a>
        <a href="/privacy.html" className={row}>Privacy policy</a>
      </section>
      {session && <Button variant="outline" className="min-h-11" onClick={() => void signOut()}>Sign out</Button>}
    </main>
  )
}

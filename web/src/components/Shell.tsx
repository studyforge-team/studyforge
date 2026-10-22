import { useEffect, useState, type ReactNode } from 'react'
import { Dialog } from '@base-ui/react/dialog'
import Auth, { useSession } from '@/components/Auth'
import { Mark } from '@/components/icons'
import { supabase } from '@/lib/supabase'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts
const link = 'flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground aria-[current=page]:bg-tint aria-[current=page]:font-semibold aria-[current=page]:text-primary'
const icon = { width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', 'aria-hidden': true } as const
// pages outside the menu still get their own title, so the top bar never says "Today" on them
const extra = [['#privacy', 'Your data'], ['#prep/', 'Prep pack']]
const links: [string, string, (h: string) => boolean][] = [
  ['#notices', 'Notices', (h) => h === '#notices'],
  ['#solve', 'Ask', (h) => h === '#solve'],
  ['#history', 'History', (h) => h.startsWith('#history')],
  ['#quiz', 'Quiz', (h) => h === '#quiz'],
  ['#interview-bank', 'Interview Bank', (h) => h === '#interview-bank'],
  ['#pyq-predictor', 'PYQ Predictor', (h) => h === '#pyq-predictor'],
  ['#time-to-finish', 'Time to Finish', (h) => h === '#time-to-finish'],
  ['#chemlab', 'ChemLab', (h) => h.startsWith('#chemlab')],
  ['#oa', 'OA Prep', (h) => h === '#oa' || h.startsWith('#oa?')],
  ['#settings', 'Settings', (h) => h === '#settings'], // in the menu for everyone, so the theme is reachable signed out too
]
const other = (h: string) => links.some(([, , m]) => m(h)) || extra.some(([k]) => h.startsWith(k)) // not Today

export default function Shell({ hash, children }: { hash: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const session = useSession()
  useEffect(() => setOpen(false), [hash]) // picking a link (or any navigation) closes the drawer
  const title = links.find(([, , m]) => m(hash))?.[1] ?? extra.find(([k]) => hash.startsWith(k))?.[1] ?? 'Today'
  const who = session && (session.user.is_anonymous ? 'Demo student' : session.user.email ?? 'Account')
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <header className="sticky top-0 z-10 border-b bg-card print:hidden">
        <div className="mx-auto flex h-14 max-w-3xl items-center gap-3 px-4">
          <Dialog.Trigger aria-label="Menu" aria-controls="sf-menu" className="-ml-2 inline-flex size-11 shrink-0 items-center justify-center rounded-lg hover:bg-muted">
            <svg {...icon}><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </Dialog.Trigger>
          <span className="flex shrink-0 items-center gap-2 font-semibold tracking-tight text-primary"><Mark />StudyForge</span>
          <span className="ml-auto min-w-0 truncate text-sm text-muted-foreground">{title}</span>
        </div>
      </header>
      {/* keepMounted: the links stay in the DOM while closed (base-ui just hides the popup) */}
      <Dialog.Portal keepMounted>
        <Dialog.Backdrop className="fixed inset-0 z-20 bg-black/50 transition-opacity data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 print:hidden" />
        <Dialog.Popup id="sf-menu" aria-label="Menu" className="fixed inset-y-0 left-0 z-30 flex w-72 max-w-[85vw] flex-col border-r bg-card transition-transform data-[ending-style]:-translate-x-full data-[starting-style]:-translate-x-full print:hidden">
          <div className="flex h-14 shrink-0 items-center justify-between border-b px-4">
            <span className="flex items-center gap-2 font-semibold tracking-tight text-primary"><Mark />StudyForge</span>
            <Dialog.Close aria-label="Close menu" className="-mr-2 inline-flex size-11 items-center justify-center rounded-lg hover:bg-muted">
              <svg {...icon}><path d="M6 6l12 12M18 6L6 18" /></svg>
            </Dialog.Close>
          </div>
          <nav aria-label="Main" className="flex-1 space-y-1 overflow-y-auto p-2">
            <a href="#" className={link} aria-current={other(hash) ? undefined : 'page'}>Today</a>
            {links.map(([href, name, m]) => <a key={href} href={href} className={link} aria-current={m(hash) ? 'page' : undefined}>{name}</a>)}
          </nav>
          {supabase && who && (
            <a href="#settings" aria-label={`Settings, signed in as ${who}`} className="flex min-h-14 shrink-0 items-center gap-3 border-t px-4 hover:bg-muted">
              <span aria-hidden="true" className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold uppercase text-primary-foreground">{who[0]}</span>
              <span className="min-w-0 truncate text-sm">{who}</span>
            </a>
          )}
        </Dialog.Popup>
      </Dialog.Portal>
      <Auth />
      {demo && (
        <div role="status" className="border-b border-warn-line bg-warn-bg print:hidden">
          <p className="mx-auto max-w-3xl px-4 py-2 text-xs text-warn sm:text-sm">Demo mode — sample answers. Nemotron connects when the backend is live.</p>
        </div>
      )}
      {children}
      <footer className="mx-auto max-w-3xl px-4 pb-4 print:hidden">
        <a href="/privacy.html" className="inline-flex min-h-11 items-center text-xs text-muted-foreground hover:text-foreground">Privacy</a>
        <a href="#privacy" className="ml-4 inline-flex min-h-11 items-center text-xs text-muted-foreground hover:text-foreground">Your data</a>
      </footer>
    </Dialog.Root>
  )
}

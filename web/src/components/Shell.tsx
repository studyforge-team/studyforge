import { useEffect, type ReactNode } from 'react'
import Auth from '@/components/Auth'
import { Mark } from '@/components/icons'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts
const link = 'inline-flex min-h-11 min-w-11 shrink-0 items-center whitespace-nowrap justify-center border-b-2 px-2 text-sm font-medium aria-[current=page]:border-primary aria-[current=page]:font-semibold aria-[current=page]:text-primary border-transparent text-muted-foreground hover:text-foreground'

export default function Shell({ hash, children }: { hash: string; children: ReactNode }) {
  const ask = hash === '#solve'
  const lab = hash.startsWith('#chemlab')
  const quiz = hash === '#quiz'
  const oa = hash === '#oa'
  const interviewBank = hash === '#interview-bank'
  useEffect(() => {
    // On narrow phones the nav scrolls; keep the current page's link in view.
    document.querySelector('nav[aria-label="Main"] [aria-current="page"]')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [hash])
  return (
    <>
      <header className="sticky top-0 z-10 border-b bg-card print:hidden">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <span className="flex shrink-0 items-center gap-2 font-semibold tracking-tight text-primary"><Mark />StudyForge</span>
          <nav aria-label="Main" className="flex min-w-0 overflow-x-auto">{/* scrolls inside the header on narrow phones instead of widening the page */}
            <a href="#" className={link} aria-current={ask || lab || quiz || oa || interviewBank ? undefined : 'page'}>Today</a>
            <a href="#solve" className={link} aria-current={ask ? 'page' : undefined}>Ask</a>
            <a href="#quiz" className={link} aria-current={quiz ? 'page' : undefined}>Quiz</a>
            <a href="#interview-bank" className={link} aria-current={interviewBank ? 'page' : undefined}>Interview Bank</a>
            <a href="#chemlab" className={link} aria-current={lab ? 'page' : undefined}>ChemLab</a>
            <a href="#oa" className={link} aria-current={oa ? 'page' : undefined}>OA Prep</a>
          </nav>
        </div>
      </header>
      <Auth />
      {demo && (
        <div role="status" className="border-b border-warn-line bg-warn-bg print:hidden">
          <p className="mx-auto max-w-3xl px-4 py-2 text-xs text-warn sm:text-sm">Demo mode — sample answers. Nemotron connects when the backend is live.</p>
        </div>
      )}
      {children}
      <footer className="mx-auto max-w-3xl px-4 pb-4 print:hidden">
        <a href="/privacy.html" className="inline-flex min-h-11 items-center text-xs text-muted-foreground hover:text-foreground">Privacy</a>
      </footer>
    </>
  )
}

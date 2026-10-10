import type { ReactNode } from 'react'
import { Mark } from '@/components/icons'

const demo = !import.meta.env.VITE_API_URL // same switch as api/client.ts
const link = 'inline-flex min-h-11 min-w-11 items-center justify-center border-b-2 px-2 text-sm font-medium aria-[current=page]:border-primary aria-[current=page]:font-semibold aria-[current=page]:text-primary border-transparent text-muted-foreground hover:text-foreground'

export default function Shell({ hash, children }: { hash: string; children: ReactNode }) {
  const ask = hash === '#solve'
  const lab = hash.startsWith('#chemlab')
  return (
    <>
      <header className="sticky top-0 z-10 border-b bg-card print:hidden">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <span className="flex items-center gap-2 font-semibold tracking-tight text-primary"><Mark />StudyForge</span>
          <nav aria-label="Main" className="flex">
            <a href="#" className={link} aria-current={ask || lab ? undefined : 'page'}>Today</a>
            <a href="#solve" className={link} aria-current={ask ? 'page' : undefined}>Ask</a>
            <a href="#chemlab" className={link} aria-current={lab ? 'page' : undefined}>ChemLab</a>
          </nav>
        </div>
      </header>
      {demo && (
        <div role="status" className="border-b border-warn-line bg-warn-bg print:hidden">
          <p className="mx-auto max-w-3xl px-4 py-2 text-xs text-warn sm:text-sm">Demo mode — sample answers. Nemotron connects when the backend is live.</p>
        </div>
      )}
      {children}
    </>
  )
}

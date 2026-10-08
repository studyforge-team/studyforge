import 'katex/dist/katex.min.css'
import { lazy, Suspense } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'
import type { Step } from '@/api/types'
import { ShieldCheck } from '@/components/icons'
import { Button } from '@/components/ui/button'

// Separate chunk: mermaid loads only when an answer actually has a diagram.
const Diagram = lazy(() => import('./Diagram'))

type Final = Extract<Step, { type: 'final' }>
const badge = { high: 'bg-muted text-foreground', medium: 'bg-warn-bg text-warn border-warn-line', low: 'bg-warn-bg text-warn border-warn-line' }

export default function AnswerCard({ a, ran = false }: { a: Final; ran?: boolean }) {
  const low = a.confidence === 'low'
  return (
    <section aria-label="Answer" className={`sf-in mt-6 space-y-4 rounded-lg border p-4 sm:p-6 print:border-0 print:p-0 ${low ? 'border-2 border-warn-line bg-warn-bg/40' : 'bg-card'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`inline-block rounded-full border px-3 py-1 text-xs font-medium ${badge[a.confidence]}`}>
          Confidence: <span data-testid="confidence">{a.confidence}</span>
        </span>
        {ran && a.confidence === 'high' && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-tint px-3 py-1 text-xs font-medium text-primary"><ShieldCheck />Computed in your browser</span>
        )}
      </div>
      {low && <p className="text-sm font-semibold text-warn">Not verified — check this answer</p>}
      {/* ponytail: no rehype-raw, so model text cannot inject HTML */}
      <div className="break-words leading-relaxed [&_.katex-display]:my-3 [&_.katex-display]:overflow-x-auto [&_.katex-display]:py-1 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs [&_p]:my-2 [&_strong]:text-lg [&_strong]:font-semibold [&_strong]:text-primary">
        <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{a.answer_md}</Markdown>
      </div>
      {a.figures.map((f, i) => (
        <figure key={i} className="break-inside-avoid rounded-lg border bg-white p-2">
          <img src={f} alt={`Figure ${i + 1}`} className="mx-auto max-w-full" />
          <figcaption className="mt-1 text-center text-xs text-muted-foreground">Figure {i + 1}</figcaption>
        </figure>
      ))}
      {a.diagram_mermaid && (
        <div className="break-inside-avoid">
          <Suspense fallback={<p className="text-sm text-muted-foreground">Drawing diagram…</p>}><Diagram src={a.diagram_mermaid} /></Suspense>
        </div>
      )}
      {a.sources.length > 0 && (
        <div className="border-t pt-3 text-xs text-muted-foreground">
          <p className="font-semibold uppercase tracking-wider">Sources</p>
          <ol className="mt-1 list-decimal space-y-0.5 pl-5">
            {a.sources.map((s, i) => (
              <li key={i}>
                {s.url ? <a href={s.url} rel="noopener noreferrer" target="_blank" className="underline">{s.title}</a> : s.title}
              </li>
            ))}
          </ol>
        </div>
      )}
      {/* ponytail: browser Save as PDF via the print dialog, no PDF library */}
      <div className="flex justify-end print:hidden">
        <Button variant="outline" onClick={() => window.print()}>Download PDF</Button>
      </div>
    </section>
  )
}

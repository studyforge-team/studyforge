import 'katex/dist/katex.min.css'
import { lazy, Suspense } from 'react'
import Markdown from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'
import type { Step } from '@/api/types'
import { Button } from '@/components/ui/button'

// Separate chunk: mermaid loads only when an answer actually has a diagram.
const Diagram = lazy(() => import('./Diagram'))

type Final = Extract<Step, { type: 'final' }>
const badge = { high: 'bg-green-100 text-green-800', medium: 'bg-amber-100 text-amber-800', low: 'bg-red-100 text-red-800' }

export default function AnswerCard({ a }: { a: Final }) {
  return (
    <section aria-label="Answer" className="mt-6 space-y-4 rounded-lg border p-4 print:border-0 print:p-0">
      <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${badge[a.confidence]}`}>
        Confidence: <span data-testid="confidence">{a.confidence}</span>
      </span>
      {a.confidence === 'low' && <p className="text-sm font-medium text-red-700">Not verified — check this answer</p>}
      {/* ponytail: no rehype-raw, so model text cannot inject HTML */}
      <div className="break-words [&_.katex-display]:overflow-x-auto [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-muted [&_pre]:p-2 [&_p]:my-2">
        <Markdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>{a.answer_md}</Markdown>
      </div>
      {a.figures.map((f, i) => (
        <img key={i} src={f} alt={`Figure ${i + 1}`} className="max-w-full break-inside-avoid" />
      ))}
      {a.diagram_mermaid && (
        <div className="break-inside-avoid">
          <Suspense fallback={<p>Drawing diagram…</p>}><Diagram src={a.diagram_mermaid} /></Suspense>
        </div>
      )}
      {a.sources.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-muted-foreground">
          {a.sources.map((s, i) => (
            <li key={i}>
              {s.url ? <a href={s.url} rel="noopener noreferrer" target="_blank" className="underline">{s.title}</a> : s.title}
            </li>
          ))}
        </ul>
      )}
      {/* ponytail: browser Save as PDF via the print dialog, no PDF library */}
      <Button variant="outline" className="print:hidden" onClick={() => window.print()}>Download PDF</Button>
    </section>
  )
}

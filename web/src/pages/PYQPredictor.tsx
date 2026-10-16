import { useEffect, useMemo, useState } from 'react'
import { readPdf } from '@/api/client'
import { Button } from '@/components/ui/button'
import { friendly, HttpError } from '@/lib/errors'
import { predict, type Prediction, type Trend } from '@/lib/pyq'

const MIN = 2
const MAX = 8
const STORE = 'studyforge.pyq.v1' // per-browser draft, so leaving the page keeps the pasted papers

const field = 'mt-2 min-h-28 w-full rounded-lg border border-input bg-background px-3 py-2 text-base'

const TREND: Record<Trend, string> = {
  rising: '↑ rising',
  steady: '→ steady',
  falling: '↓ falling',
  new: '★ new in the latest paper',
}

function loadPapers(): string[] {
  try {
    const v: unknown = JSON.parse(localStorage.getItem(STORE) ?? 'null')
    if (Array.isArray(v) && v.length >= MIN && v.length <= MAX && v.every((x) => typeof x === 'string')) return v
  } catch {
    // storage blocked or damaged: start empty
  }
  return ['', '', '']
}

function pct(x: number): string {
  return `${Math.round(x * 100)}%`
}

export default function PYQPredictor() {
  const [papers, setPapers] = useState<string[]>(loadPapers)
  const [error, setError] = useState('')
  const [result, setResult] = useState<Prediction | null>(null)
  const [pdfNote, setPdfNote] = useState<{ index: number; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify(papers))
    } catch {
      // private window: the page still works, the draft just isn't kept
    }
  }, [papers])

  const filled = useMemo(() => papers.filter((p) => p.trim()), [papers])

  function edit(index: number, value: string) {
    setPapers((cur) => cur.map((p, i) => (i === index ? value : p)))
    setResult(null) // results always match the papers on screen
    setError('')
  }

  // PY: a past paper's PDF fills its box with the PDF's own text (questions split by line, as when pasted).
  async function pickPdf(index: number, file: File | undefined, input: HTMLInputElement) {
    if (!file) return
    setBusy(true)
    setPdfNote({ index, text: 'Reading the PDF…' })
    try {
      const r = await readPdf(file, () => setPdfNote({ index, text: 'Waking up the server…' }))
      if (!r.words) {
        setPdfNote({ index, text: 'This PDF has no text layer (probably a scan). Paste or type its questions instead.' })
        return
      }
      edit(index, r.text.filter(Boolean).join('\n'))
      setPdfNote({ index, text: `${file.name}: text of ${r.pages} page${r.pages === 1 ? '' : 's'} added. Check it before predicting.` })
    } catch (e) {
      const st = e instanceof HttpError ? e.status : 0
      setPdfNote({ index, text: st === 415 ? 'That file is not a readable PDF.' : st === 413 ? 'That PDF is over 10 MB.' : st === 401 ? 'Sign in to read a PDF.' : friendly(e) })
    } finally {
      setBusy(false)
      input.value = '' // picking the same file again reads it again
    }
  }

  function run() {
    setError('')
    setResult(null)
    if (filled.length < MIN) {
      setError(`Paste at least ${MIN} past papers (oldest first) to see which topics keep coming back.`)
      return
    }
    const r = predict(filled)
    if (r.papers < MIN) {
      setError(`Only ${r.papers} of the pasted papers contain questions. Paste the question text of at least ${MIN} papers.`)
      return
    }
    if (r.stats.length === 0) {
      setError('No chemical engineering topics were recognised. Paste the question text itself (one question per line or numbered Q1, Q2, …).')
      return
    }
    setResult(r)
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <header>
        <p className="text-sm text-muted-foreground">Study tools · Exam preparation</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">PYQ Predictor</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Paste {MIN} to {MAX} past papers, oldest first. StudyForge counts how much of each paper (by marks when every
          question shows them, otherwise by number of questions) goes to each chemical engineering topic, gives recent papers more
          weight, and shows which topics are rising.
        </p>
      </header>

      <section className="mt-6 space-y-4 rounded-lg border bg-card p-4 sm:p-5">
        {papers.map((paper, index) => {
          const label = `Past paper ${index + 1}${index === 0 ? ' (oldest)' : index === papers.length - 1 ? ' (newest)' : ''}`
          return (
            <div key={index}>
              <div className="flex items-center justify-between gap-2">
                <label htmlFor={`past-paper-${index + 1}`} className="block text-sm font-medium">
                  {label}
                </label>
                {papers.length > MIN && (
                  <button
                    type="button"
                    className="min-h-11 px-2 text-sm text-muted-foreground underline hover:text-foreground"
                    aria-label={`Remove past paper ${index + 1}`}
                    disabled={busy} // a PDF being read fills its box by position
                    onClick={() => {
                      setPapers((cur) => cur.filter((_, i) => i !== index))
                      setPdfNote(null) // its box index no longer matches
                      setResult(null)
                      setError('')
                    }}
                  >
                    Remove
                  </button>
                )}
              </div>
              <textarea
                id={`past-paper-${index + 1}`}
                className={field}
                placeholder="Q1. Derive the design equation of a CSTR … (10 marks)"
                value={paper}
                onChange={(event) => edit(index, event.target.value)}
              />
              <label htmlFor={`past-paper-pdf-${index + 1}`} className="mt-2 block text-sm text-muted-foreground">Or pick past paper {index + 1} as a PDF:</label>
              <input id={`past-paper-pdf-${index + 1}`} type="file" accept="application/pdf,.pdf" disabled={busy} className="mt-1 block min-h-11 w-full text-sm" onChange={(e) => void pickPdf(index, e.target.files?.[0], e.target)} />
              {pdfNote?.index === index && <p role="status" className="mt-1 text-sm text-muted-foreground">{pdfNote.text}</p>}
            </div>
          )
        })}

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={run}>Predict topics</Button>
          {papers.length < MAX && (
            <Button
              variant="outline"
              onClick={() => {
                setPapers((cur) => [...cur, ''])
                setResult(null)
                setError('')
              }}
            >
              Add another paper
            </Button>
          )}
        </div>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </section>

      {result && (
        <section className="mt-6 space-y-6">
          <p role="status" className="text-sm text-muted-foreground">
            Read {result.papers} papers and {result.questions} question{result.questions === 1 ? '' : 's'}. Weighted by{' '}
            {result.usedMarks ? 'marks' : 'number of questions (not every question showed its marks)'}.
          </p>

          <div>
            <h2 className="text-lg font-semibold">Topic frequency</h2>
            <div className="mt-3 overflow-x-auto rounded-lg border">
              <table aria-label="Topic frequency" className="w-full text-left text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th scope="col" className="px-3 py-3 font-medium">Topic</th>
                    <th scope="col" className="px-3 py-3 font-medium">Papers</th>
                    <th scope="col" className="px-3 py-3 font-medium">Questions</th>
                    <th scope="col" className="px-3 py-3 font-medium">Weighted share</th>
                    <th scope="col" className="px-3 py-3 font-medium">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {result.stats.map((s) => (
                    <tr key={s.topic} className="border-t">
                      <td className="px-3 py-3">{s.topic}</td>
                      <td className="px-3 py-3 tabular-nums">{s.papers} / {result.papers}</td>
                      <td className="px-3 py-3 tabular-nums">{s.questions}</td>
                      <td className="px-3 py-3 tabular-nums">{pct(s.share)}</td>
                      <td className="px-3 py-3 whitespace-nowrap">{TREND[s.trend]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Weighted share = part of each paper on this topic, averaged with the newest paper counting most. A question can
              touch several topics, so shares can add up to more than 100%.
            </p>
          </div>

          <div>
            <h2 className="text-lg font-semibold">Likely practice paper</h2>
            <ol className="mt-3 space-y-3">
              {result.stats.slice(0, 5).map((s, index) => (
                <li key={s.topic} className="rounded-lg border bg-card p-4">
                  <p className="text-xs text-muted-foreground">
                    Question {index + 1} · {s.topic} · in {s.papers} of {result.papers} papers · {TREND[s.trend]}
                  </p>
                  <p className="mt-2 text-sm font-medium">{s.question}</p>
                </li>
              ))}
            </ol>
          </div>

          {result.unclassified.length > 0 && (
            <details className="rounded-lg border p-3 text-sm">
              <summary className="cursor-pointer">
                {result.unclassified.length} question{result.unclassified.length === 1 ? '' : 's'} matched no topic
              </summary>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
                {result.unclassified.slice(0, 20).map((q, i) => (
                  <li key={i}>{q.length > 140 ? `${q.slice(0, 140)}…` : q}</li>
                ))}
              </ul>
            </details>
          )}

          <p className="rounded-lg border p-3 text-sm text-muted-foreground">
            Estimate only: based on the papers you pasted and a fixed list of chemical engineering topics. These are not
            guaranteed exam questions, and topics missing from these papers can still appear.
          </p>
        </section>
      )}
    </main>
  )
}

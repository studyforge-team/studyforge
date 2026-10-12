
import { useState } from 'react'

const MIN_MINUTES_PER_PAGE = 1
const MAX_MINUTES_PER_PAGE = 3
const MAX_PAGES = 10000

function formatDuration(minutes: number) {
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const remaining = minutes % 60
  return remaining ? `${hours} hr ${remaining} min` : `${hours} hr`
}

export default function TimeToFinish() {
  const [pageInput, setPageInput] = useState('30')
  const pages = Number(pageInput)
  const valid =
    pageInput.trim() !== '' &&
    Number.isInteger(pages) &&
    pages >= 1 &&
    pages <= MAX_PAGES

  const lower = valid ? pages * MIN_MINUTES_PER_PAGE : 0
  const upper = valid ? pages * MAX_MINUTES_PER_PAGE : 0

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">
        Time to Finish
      </h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Estimate how long you might need to work through a document.
      </p>

      <section className="mt-5 rounded-lg border bg-card p-4 sm:p-5">
        <label htmlFor="page-count" className="block text-sm font-medium">
          Number of pages
        </label>
        <input
          id="page-count"
          type="number"
          min={1}
          max={MAX_PAGES}
          step={1}
          value={pageInput}
          onChange={(event) => setPageInput(event.target.value)}
          aria-invalid={!valid}
          aria-describedby="page-help"
          className="mt-2 min-h-11 w-full rounded-lg border border-input bg-background px-3 text-base"
        />
        <p id="page-help" className="mt-2 text-sm text-muted-foreground">
          Enter the page count from your PDF. Demo mode does not extract it
          automatically.
        </p>

        {!valid && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            Enter a whole number from 1 to {MAX_PAGES}.
          </p>
        )}
      </section>

      {valid && (
        <section
          aria-label="Time estimate"
          className="mt-4 rounded-lg border bg-card p-5"
        >
          <p className="text-sm font-medium text-muted-foreground">
            Estimated time for {pages} {pages === 1 ? 'page' : 'pages'}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight">
            {formatDuration(lower)}–{formatDuration(upper)}
          </p>
          <p className="mt-3 text-sm text-muted-foreground">
            Rough estimate, not a prediction based on PDF contents. This
            range assumes 1–3 minutes per page; diagrams, exercises, and
            revision can take longer.
          </p>
        </section>
      )}
    </main>
  )
}

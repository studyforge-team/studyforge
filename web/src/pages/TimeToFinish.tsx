import { useState } from 'react'
import { readPdf } from '@/api/client'
import { friendly, HttpError } from '@/lib/errors'
import {
  estimate,
  formatDuration,
  MAX_COUNT,
  MAX_PASSES,
  parseDate,
  RATES,
  REVISION_FACTOR,
  type Material,
} from '@/lib/estimate'

const field = 'mt-2 min-h-11 w-full rounded-lg border border-input bg-background px-3 text-base'

// A whole number from 1 to max, or null. Accepts only plain digits (no "1e2", "3.0", "-2").
function wholeNumber(text: string, max: number): number | null {
  if (!/^\d+$/.test(text.trim())) return null
  const n = Number(text.trim())
  return n >= 1 && n <= max ? n : null
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

export default function TimeToFinish() {
  const [material, setMaterial] = useState<Material>('textbook')
  const [countText, setCountText] = useState('30')
  const [pdfNote, setPdfNote] = useState('')
  const [pdfBusy, setPdfBusy] = useState(false)
  const [passes, setPasses] = useState(1)
  const [paceMinutes, setPaceMinutes] = useState('')
  const [paceCount, setPaceCount] = useState('')
  const [deadline, setDeadline] = useState('')
  const [today] = useState(() => new Date()) // read once, so the estimate doesn't shift between renders

  const unit = RATES[material].unit
  const count = wholeNumber(countText, MAX_COUNT)

  // TE: the page count comes from the PDF itself; the estimate still uses the stated rates.
  const pickPdf = async (file: File | undefined, input: HTMLInputElement) => {
    if (!file) return
    setPdfBusy(true)
    setPdfNote('Reading the PDF…')
    try {
      const r = await readPdf(file, () => setPdfNote('Waking up the server…'))
      setCountText(String(Math.min(r.pages, MAX_COUNT)))
      setPdfNote(`${file.name}: ${plural(r.pages, 'page')}${r.words ? '' : ' (no text layer, so it may be a scan; pages still count)'}.`)
    } catch (e) {
      const s = e instanceof HttpError ? e.status : 0
      setPdfNote(`${s === 415 ? 'That file is not a readable PDF.' : s === 413 ? 'That PDF is over 10 MB.' : s === 401 ? 'Sign in to read a PDF.' : friendly(e)} Type the number of pages instead.`)
    } finally {
      setPdfBusy(false)
      input.value = '' // picking the same file again reads it again
    }
  }
  // The pace is used only when both boxes are filled; one box alone is a hint, not an error.
  const paceGiven = paceMinutes.trim() !== '' && paceCount.trim() !== ''
  const paceHalf = !paceGiven && (paceMinutes.trim() !== '' || paceCount.trim() !== '')
  const pm = wholeNumber(paceMinutes, MAX_COUNT)
  const pc = wholeNumber(paceCount, MAX_COUNT)
  const paceOk = !paceGiven || (pm !== null && pc !== null)
  const deadlineOk = deadline === '' || parseDate(deadline) !== null

  const errors = [
    count === null && `Enter the number of ${unit}s as a whole number from 1 to ${MAX_COUNT}.`,
    !paceOk && `Your pace needs whole numbers from 1 to ${MAX_COUNT} in both boxes.`,
    !deadlineOk && 'Enter the deadline as a valid date.',
  ].filter(Boolean) as string[]

  // Cheap to compute, so it is simply recomputed on every render.
  const result =
    errors.length === 0 && count !== null
      ? estimate({
          material,
          count,
          passes,
          pace: paceGiven && pm !== null && pc !== null ? { minutes: pm, count: pc } : null,
          deadline: deadline || null,
          today,
        })
      : null

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Time to Finish</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Estimate how long your study material will take, and how much to do each day before a deadline.
      </p>

      <section className="mt-5 space-y-5 rounded-lg border bg-card p-4 sm:p-5">
        <fieldset disabled={pdfBusy /* a PDF being read fills the page count */}>
          <legend className="text-sm font-medium">Type of material</legend>
          <div className="mt-2 space-y-1">
            {(Object.keys(RATES) as Material[]).map((m) => (
              <label key={m} className="flex min-h-11 items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="material"
                  value={m}
                  checked={material === m}
                  onChange={() => {
                    setMaterial(m)
                    // a pace measured on one kind of material does not carry over to another
                    setPaceMinutes('')
                    setPaceCount('')
                  }}
                />
                {RATES[m].label} ({RATES[m].min}–{RATES[m].max} min per {RATES[m].unit})
              </label>
            ))}
          </div>
        </fieldset>

        <div>
          <label htmlFor="ttf-count" className="block text-sm font-medium">
            Number of {unit}s
          </label>
          <input
            id="ttf-count"
            disabled={pdfBusy}
            inputMode="numeric"
            value={countText}
            onChange={(e) => setCountText(e.target.value)}
            aria-invalid={count === null}
            className={field}
          />
          {unit === 'page' && (
            <div className="mt-2 text-sm">
              <label htmlFor="ttf-pdf" className="text-muted-foreground">Or pick the PDF to count its pages: </label>
              <input id="ttf-pdf" type="file" accept="application/pdf,.pdf" disabled={pdfBusy} className="mt-1 block min-h-11 w-full text-sm" onChange={(e) => void pickPdf(e.target.files?.[0], e.target)} />
              {pdfNote && <p role="status" className="mt-1 text-muted-foreground">{pdfNote}</p>}
            </div>
          )}
        </div>

        <div>
          <label htmlFor="ttf-passes" className="block text-sm font-medium">
            Rounds through the material
          </label>
          <select id="ttf-passes" value={passes} onChange={(e) => setPasses(Number(e.target.value))} className={field}>
            {Array.from({ length: MAX_PASSES }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n === 1 ? '1 (first read only)' : `${n} (first read + ${n - 1} revision${n > 2 ? 's' : ''})`}
              </option>
            ))}
          </select>
        </div>

        <fieldset>
          <legend className="text-sm font-medium">Your own pace (optional, more accurate)</legend>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <span>I took</span>
            <input
              aria-label="Minutes you took"
              aria-invalid={paceGiven && pm === null}
              inputMode="numeric"
              value={paceMinutes}
              onChange={(e) => setPaceMinutes(e.target.value)}
              className="min-h-11 w-20 rounded-lg border border-input bg-background px-2 text-base"
            />
            <span>minutes for</span>
            <input
              aria-label={`Number of ${unit}s you did in that time`}
              aria-invalid={paceGiven && pc === null}
              inputMode="numeric"
              value={paceCount}
              onChange={(e) => setPaceCount(e.target.value)}
              className="min-h-11 w-20 rounded-lg border border-input bg-background px-2 text-base"
            />
            <span>{unit}s.</span>
          </div>
          {paceHalf && (
            <p className="mt-2 text-sm text-muted-foreground" data-testid="ttf-pace-hint">
              Fill in both boxes to use your own pace; until then the typical rate is used.
            </p>
          )}
        </fieldset>

        <div>
          <label htmlFor="ttf-deadline" className="block text-sm font-medium">
            Deadline (optional)
          </label>
          <input id="ttf-deadline" type="date" aria-invalid={!deadlineOk} value={deadline} onChange={(e) => setDeadline(e.target.value)} className={field} />
        </div>

        {errors.length > 0 && (
          <div role="alert" className="space-y-1 text-sm text-destructive">
            {errors.map((e) => (
              <p key={e}>{e}</p>
            ))}
          </div>
        )}
      </section>

      {result && count !== null && (
        <section aria-label="Time estimate" className="mt-4 rounded-lg border bg-card p-5">
          <p className="text-sm font-medium text-muted-foreground">
            Estimated time for {plural(count, unit)}
            {passes > 1 ? `, ${passes} rounds` : ''}
          </p>
          <p className="mt-2 text-3xl font-semibold tracking-tight" data-testid="ttf-total">
            {formatDuration(result.low)}–{formatDuration(result.high)}
          </p>

          {result.daysLeft !== null && (
            <p className="mt-3 text-sm" data-testid="ttf-per-day">
              {result.overdue
                ? 'This deadline has already passed.'
                : result.daysLeft === 0
                  ? 'The deadline is today: all of it would have to fit into today.'
                  : `About ${formatDuration(result.perDayLow ?? 0)}–${formatDuration(result.perDayHigh ?? 0)} per day for the next ${plural(result.daysLeft, 'day')}.`}
            </p>
          )}

          <p className="mt-3 text-sm text-muted-foreground" data-testid="ttf-basis">
            Based on{' '}
            {result.fromPace
              ? `your pace of ${formatDuration(result.perUnitLow)}–${formatDuration(result.perUnitHigh)} per ${unit} (your time ±20 %)`
              : `a typical ${RATES[material].min}–${RATES[material].max} min per ${unit} for this material`}
            {passes > 1 ? `, with each revision round taking about ${Math.round(REVISION_FACTOR * 100)} % of the first read` : ''}.
            A rough estimate: breaks, difficult topics and practice can take longer.
          </p>
        </section>
      )}
    </main>
  )
}

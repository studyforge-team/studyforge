// Time-to-finish estimate: pure functions, no I/O. All numbers come from the student's
// inputs and the stated per-unit assumptions below; nothing is guessed from file contents.

export type Material = 'slides' | 'textbook' | 'problems'

// Typical study time per unit, in minutes (shown on the page, so the student sees the assumption).
export const RATES: Record<Material, { label: string; unit: string; min: number; max: number }> = {
  slides: { label: 'Slides or short notes', unit: 'page', min: 1, max: 3 },
  textbook: { label: 'Textbook or lecture notes with derivations', unit: 'page', min: 4, max: 8 },
  problems: { label: 'Numerical problems to solve', unit: 'problem', min: 10, max: 20 },
}

export const REVISION_FACTOR = 0.4 // each extra round takes about 40 % of the first pass
export const PACE_SPREAD = 0.2 // a personal pace is used as ±20 %
export const MAX_COUNT = 10000
export const MAX_PASSES = 5

export type EstimateInput = {
  material: Material
  count: number // pages or problems
  passes: number // 1 = first read only
  pace: { minutes: number; count: number } | null // "I took 20 min for 5 pages"
  deadline: string | null // YYYY-MM-DD, local date
  today: Date
}

export type Estimate = {
  low: number // total minutes
  high: number
  perUnitLow: number // minutes per page/problem used
  perUnitHigh: number
  fromPace: boolean
  daysLeft: number | null // whole days from today until the deadline day (0 = due today or past)
  overdue: boolean // the deadline day is before today
  perDayLow: number | null // minutes per day until the deadline
  perDayHigh: number | null
}

function localDay(d: Date): number {
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86_400_000
}

export function parseDate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  return d.getMonth() === Number(m[2]) - 1 && d.getDate() === Number(m[3]) ? d : null
}

export function estimate(input: EstimateInput): Estimate {
  const typical = RATES[input.material]
  const rate = input.pace ? input.pace.minutes / input.pace.count : null
  const perUnitLow = rate === null ? typical.min : rate * (1 - PACE_SPREAD)
  const perUnitHigh = rate === null ? typical.max : rate * (1 + PACE_SPREAD)
  const rounds = 1 + REVISION_FACTOR * (input.passes - 1)
  // Kept unrounded: formatDuration rounds for display and shows "<1 min" instead of "0 min".
  const low = input.count * perUnitLow * rounds
  const high = input.count * perUnitHigh * rounds

  const due = input.deadline ? parseDate(input.deadline) : null
  const diff = due ? localDay(due) - localDay(input.today) : null
  const daysLeft = diff === null ? null : Math.max(0, diff)
  return {
    low,
    high,
    perUnitLow,
    perUnitHigh,
    fromPace: rate !== null,
    daysLeft,
    overdue: diff !== null && diff < 0,
    perDayLow: daysLeft ? low / daysLeft : null,
    perDayHigh: daysLeft ? high / daysLeft : null,
  }
}

export function formatDuration(minutes: number): string {
  if (minutes > 0 && minutes < 0.5) return '<1 min'
  const m = Math.max(1, Math.round(minutes))
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  const rest = m % 60
  return rest ? `${h} hr ${rest} min` : `${h} hr`
}

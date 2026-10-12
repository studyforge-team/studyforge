// TS port of check_key / fill_solution from api/app/agent/quiz.py (Q1). Keep the reason strings identical.
import type { NumericalItem } from '@/api/types'

export type KeyCheck = { ok: true; value: number } | { ok: false; reason: string }

const real = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x)
const obj = (x: unknown): x is Record<string, unknown> => typeof x === 'object' && x !== null && !Array.isArray(x)
const fail = (reason: string): KeyCheck => ({ ok: false, reason })

// ponytail: Python's .4g switches to e-notation at >= 1e4 or < 1e-4; this prints plain digits. Fine for display.
export const fmt4 = (x: number) => String(parseFloat(x.toPrecision(4)))

export function checkKey(result: unknown, item: NumericalItem): KeyCheck {
  if (!obj(result)) return fail('not_a_dict')
  const { answer, check } = result
  if (!obj(answer)) return fail('missing_answer')
  if (!obj(check)) return fail('missing_check')
  const a = answer.value, c = check.value
  if (!real(a) || !real(c)) return fail('not_a_number')
  for (const part of [answer, check]) {
    if (typeof part.unit !== 'string' || part.unit.trim() !== item.unit.trim()) return fail('unit_mismatch')
  }
  const allowed = Math.abs(a) > 1e-12 ? item.tolerance_rel * Math.abs(a) : 1e-12
  return Math.abs(a - c) > allowed ? fail('methods_disagree') : { ok: true, value: a }
}

// Returns the filled text, or null when any placeholder has no numeric value (caller drops the item).
export function fillSolution(item: NumericalItem, result: Record<string, unknown>): string | null {
  let missing = false
  const text = item.worked_solution.replace(/\{([^{}]*)\}/g, (_, name: string) => {
    const values = result.values
    const src = name === 'answer' || name === 'check' ? result[name] : obj(values) && name in values ? values[name] : result[name]
    const v = obj(src) ? src.value : undefined
    if (!real(v)) missing = true
    return real(v) ? fmt4(v) : ''
  })
  return missing ? null : text
}

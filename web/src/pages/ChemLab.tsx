import { useEffect, useState } from 'react'
import { LineChart, type Line } from '@/components/LineChart'
import { fmt } from '@/lib/fmt'
import { Button } from '@/components/ui/button'
import { run } from '@/sandbox/client'

// gap: the frozen contract has no `final.chemlab` field, so AnswerCard has no "Open in ChemLab" button yet.
// The hook is ready: link to `#chemlab?V=2&T0=310` and those inputs pre-fill (validated, bad params ignored).
type Spec = { unit: string; default: number; min: number; max: number; description: string }
type Ser = { x: (number | null)[]; y: (number | null)[]; branches?: { stable: boolean; start: number; stop: number }[] }
type Out = {
  ok: boolean; errors: { message: string }[]; warnings: string[]
  inputs: Record<string, { value: number }>; outputs: Record<string, { value: number; unit: string }>
  steady_states: { T: number; X: number; stable: boolean }[]
  geometry: { diameter_m: number; height_m: number }; series: Record<string, Ser>
}

const SLIDERS = ['V', 'v0', 'T0', 'Ta', 'UA', 'CA0']
const num = (s: string) => (s.trim() === '' ? NaN : Number(s))
const u = (s: Spec) => (s.unit === '-' ? '' : ` ${s.unit}`)
const check = (s: Spec, v: string) => { const x = num(v); return x >= s.min && x <= s.max ? '' : `Enter a number from ${fmt(s.min)} to ${fmt(s.max)}${u(s)}.` }
// Slider window (not the validation range): typed values outside it but inside SPEC [min,max] stay valid; the slider pins to its end.
// ponytail: UA (default 0) is log with exact 0 at position 0 and floor hi*1e-6.
type Win = { lo: number; hi: number; log: boolean }
const win = (s: Spec): Win =>
  s.unit === 'K' ? { lo: Math.max(s.min, s.default - 100), hi: Math.min(s.max, s.default + 300), log: false }
    : s.default <= 0 ? { lo: 0, hi: Math.min(s.max, 1e5), log: true }
      : { lo: Math.max(s.min, s.default / 100), hi: Math.min(s.max, s.default * 100), log: true }
const floor = (w: Win) => (w.lo > 0 ? w.lo : w.hi * 1e-6)
const clamp = (p: number) => Math.min(1000, Math.max(0, Math.round(p) || 0))
const toPos = (w: Win, v: number) => clamp(w.log ? (v > 0 ? (Math.log(v / floor(w)) / Math.log(w.hi / floor(w))) * 1000 : 0) : ((v - w.lo) / (w.hi - w.lo)) * 1000)
const fromPos = (s: Spec, p: number) => {
  const w = win(s)
  const v = !w.log ? w.lo + ((w.hi - w.lo) * p) / 1000 : p === 0 && w.lo <= 0 ? 0 : floor(w) * (w.hi / floor(w)) ** (p / 1000)
  return Math.min(s.max, Math.max(s.min, v))
}
const field = 'h-11 w-full rounded-lg border border-input bg-background px-3 text-base aria-invalid:border-destructive'

export default function ChemLab() {
  const [spec, setSpec] = useState<Record<string, Spec>>()
  const [loadErr, setLoadErr] = useState('')
  const [tries, setTries] = useState(0)
  const [vals, setVals] = useState<Record<string, string>>({})
  const [out, setOut] = useState<Out>()
  const [fail, setFail] = useState('')
  const [sel, setSel] = useState(-1)

  // SPEC comes from Python (single source of truth); the first call also boots the sandbox.
  useEffect(() => {
    let live = true
    void run('from chemlab.cstr import SPEC\nresult = {k: dict(v) for k, v in SPEC.items()}', { mode: 'chemlab' }).then((r) => {
      if (!live) return
      if (!r.ok) return setLoadErr(r.error)
      const s = r.result as Record<string, Spec>
      const q = new URLSearchParams(location.hash.split('?')[1] ?? '')
      setVals(Object.fromEntries(Object.entries(s).map(([k, sp]) => { const p = q.get(k); return [k, p !== null && !check(sp, p) ? p : String(sp.default)] })))
      setSpec(s)
    })
    return () => { live = false }
  }, [tries])

  const names = spec ? Object.keys(spec) : []
  const errs = Object.fromEntries(names.map((k) => [k, check(spec![k], vals[k] ?? '')]).filter(([, e]) => e))
  const body = spec && !Object.keys(errs).length ? JSON.stringify(Object.fromEntries(names.map((k) => [k, num(vals[k])]))) : ''

  useEffect(() => {
    if (!body) return // out-of-range input: do not run
    const t = setTimeout(() => {
      void run(`from chemlab.cstr import run\nresult = run(${body})`, { mode: 'chemlab', latestWins: true }).then((r) => {
        if (r.ok) { setFail(''); setOut(r.result as Out) } else if (r.error !== 'superseded') setFail(r.error)
      })
    }, 150)
    return () => clearTimeout(t)
  }, [body])

  if (loadErr) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-6">
        <p role="alert" className="text-sm font-medium text-destructive">ChemLab could not start Python: {loadErr}</p>
        <Button className="mt-3" onClick={() => { setLoadErr(''); setTries(tries + 1) }}>Try again</Button>
      </main>
    )
  }
  if (!spec) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-6">
        <p role="status" className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className="size-5 animate-spin rounded-full border-2 border-tint border-t-primary" />Starting Python…
        </p>
      </main>
    )
  }

  const ss = out?.steady_states ?? []
  const si = sel >= 0 && sel < ss.length ? sel : Math.max(0, ss.findIndex((s) => s.stable))
  // V3Da (later): the 3D scene reads `ss[si]` (the student's selected steady state) and `out.geometry`.
  const gen = out ? (x: number) => -out.inputs.dHr.value * out.inputs.v0.value * out.inputs.CA0.value * x : () => 0
  const lines = (s: Ser): Line[] =>
    (s.branches ?? [{ stable: true, start: 0, stop: s.x.length }]).map((b) => ({
      name: s.branches ? (b.stable ? 'stable' : 'unstable') : 'conversion',
      x: s.x.slice(b.start, b.stop), y: s.y.slice(b.start, b.stop), color: b.stable ? 'var(--primary)' : 'var(--destructive)', dash: !b.stable,
    }))
  const sr = out?.series ?? {}

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">ChemLab</h1>
      <p className="mt-1 text-sm text-muted-foreground">Continuous stirred-tank reactor (CSTR). Runs on your device, no credits used.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {names.map((k) => {
          const s = spec[k]
          return k === 'isothermal' ? (
            <label key={k} className="flex min-h-11 items-start gap-3 rounded-lg border bg-card p-3 text-sm sm:col-span-2">
              <input type="checkbox" className="mt-0.5 size-5" checked={vals[k] === '1'} onChange={(e) => setVals({ ...vals, [k]: e.target.checked ? '1' : '0' })} />
              <span><span className="font-medium">Isothermal</span><span className="block text-xs text-muted-foreground">{s.description}</span></span>
            </label>
          ) : (
            <div key={k} className="rounded-lg border bg-card p-3">
              <label htmlFor={`f-${k}`} className="flex justify-between gap-2 text-sm font-medium"><span>{k}</span><span className="font-normal text-muted-foreground">{s.unit}</span></label>
              <p className="text-xs text-muted-foreground">{s.description}</p>
              <input id={`f-${k}`} type="number" step="any" inputMode="decimal" className={`mt-2 ${field}`} value={vals[k]} aria-invalid={!!errs[k]} aria-describedby={`e-${k}`}
                onChange={(e) => setVals({ ...vals, [k]: e.target.value })} />
              {SLIDERS.includes(k) && (
                <input type="range" aria-label={`${k} slider`} className="mt-1 h-11 w-full accent-primary" min={0} max={1000} step={1}
                  value={toPos(win(s), num(vals[k]))}
                  onChange={(e) => setVals({ ...vals, [k]: fmt(fromPos(s, +e.target.value)) })} />
              )}
              <p id={`e-${k}`} role="alert" className="text-xs text-destructive">{errs[k]}</p>
            </div>
          )
        })}
      </div>
      {!out && !fail && !Object.keys(errs).length && <p role="status" className="mt-4 text-sm text-muted-foreground">Calculating…</p>}
      {Object.keys(errs).length > 0 && <p className="mt-4 text-sm font-medium text-destructive">Fix the highlighted inputs to update the results.</p>}
      {fail && <p role="alert" className="mt-4 text-sm font-medium text-destructive">Calculation failed: {fail}</p>}
      {out && (
        <div className="mt-4 space-y-3" aria-live="polite">
          {out.errors.map((e, i) => <p key={i} role="alert" className="text-sm font-medium text-destructive">{e.message}</p>)}
          {out.warnings.map((w, i) => <p key={i} className="text-sm text-warn">{w}</p>)}
          {out.ok && (
            <>
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-base font-semibold">Operating point</h2>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                  {Object.entries(out.outputs).map(([k, o]) => (
                    <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd><span data-out={k} className="font-medium tabular-nums">{fmt(o.value)}</span> {o.unit === '-' ? '' : o.unit}</dd></div>
                  ))}
                  <div><dt className="text-xs text-muted-foreground">D, H</dt><dd className="font-medium tabular-nums">{fmt(out.geometry.diameter_m)} m, {fmt(out.geometry.height_m)} m</dd></div>
                </dl>
              </section>
              <fieldset className="rounded-lg border bg-card p-4">
                <legend className="px-1 text-base font-semibold">Steady states ({ss.length})</legend>
                {ss.map((s, i) => (
                  <label key={i} className="flex min-h-11 items-center gap-3 text-sm">
                    <input type="radio" name="state" className="size-5" checked={i === si} onChange={() => setSel(i)} />
                    <span>T = {fmt(s.T)} K, X = {fmt(s.X)} · <b className={s.stable ? 'text-primary' : 'text-destructive'}>{s.stable ? 'stable' : 'unstable'}</b></span>
                  </label>
                ))}
              </fieldset>
              {sr.heat_generated && sr.heat_removed && (
                <LineChart title="Heat generated and removed" xLabel="T (K)" yLabel="Heat (W)"
                  lines={[{ name: 'generated', x: sr.heat_generated.x, y: sr.heat_generated.y, color: 'var(--destructive)' }, { name: 'removed', x: sr.heat_removed.x, y: sr.heat_removed.y, color: 'var(--primary)' }]}
                  marks={ss.map((s, i) => ({ x: s.T, y: gen(s.X), color: 'currentColor', filled: s.stable, big: i === si }))} />
              )}
              {sr.s_curve && <LineChart title="S-curve: conversion vs residence time" logX xLabel="residence time (s)" yLabel="conversion X (-)" lines={lines(sr.s_curve)} />}
            </>
          )}
        </div>
      )}
    </main>
  )
}

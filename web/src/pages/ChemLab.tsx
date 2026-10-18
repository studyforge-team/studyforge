import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { LineChart, type Line } from '@/components/LineChart'
import { fmt } from '@/lib/fmt'
import { Button } from '@/components/ui/button'
import { run } from '@/sandbox/client'
import { McCabe } from '@/chemlab/drawings/McCabe'
import { cstrViews } from '@/chemlab/drawings/cstr'
import { columnViews } from '@/chemlab/drawings/column'
import { hxViews, type HxGeometry } from '@/chemlab/drawings/hx'
import { pfd } from '@/chemlab/drawings/pfd'

const Cstr3D = lazy(() => import('@/chemlab/three/Cstr3D')) // three.js stays in its own chunk
const Equip3D = lazy(() => import('@/chemlab/three/Equip3D'))

// gap: the frozen contract has no `final.chemlab` field, so AnswerCard has no "Open in ChemLab" button yet.
// The hook is ready: link to `#chemlab?V=2&T0=310` (or `#chemlab/pfr?L=3`) and those inputs pre-fill (validated, bad params ignored).
type Spec = { unit: string; default: number; min: number; max: number; description: string }
type Ser = { x: (number | null)[]; y: (number | null)[]; x_unit?: string; y_unit?: string; branches?: { stable: boolean; start: number; stop: number }[] }
type Out = {
  ok: boolean; errors: { message: string }[]; warnings: string[]
  inputs: Record<string, { value: number; unit: string }>; outputs: Record<string, { value: number; unit: string }>
  steady_states: { T: number; X: number; stable: boolean }[]
  geometry: { diameter_m: number; height_m: number; n_trays?: number; feed_tray?: number } & Partial<HxGeometry>; series: Record<string, Ser>
}

const TABS = [['cstr', 'CSTR'], ['batch', 'Batch'], ['pfr', 'PFR'], ['mccabe', 'McCabe-Thiele'], ['hx', 'Heat exchanger']]
// [series key, title, x name, y name]; axis units come from the series' own x_unit / y_unit
const CHARTS: Record<string, [string, string, string, string][]> = {
  batch: [['concentration_time', 'Concentration vs time', 'time', 'CA'], ['conversion_time', 'Conversion vs time', 'time', 'X']],
  pfr: [['concentration_profile', 'Concentration along the reactor', 'length', 'CA'], ['conversion_profile', 'Conversion along the reactor', 'length', 'X'], ['levenspiel', 'Levenspiel plot', 'X', '1/(-rA)']],
}
const ax = (n: string, unit?: string) => (unit && unit !== '-' ? `${n} (${unit})` : n)
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
  const q = new URLSearchParams(location.hash.split('?')[1] ?? '')
  // ponytail: template in the path (#chemlab/pfr?L=3), not the query: batch has its own input named `t`.
  const t = TABS.find(([n]) => n === location.hash.split('?')[0].split('/')[1])?.[0] ?? 'cstr' // whitelisted; App remounts ChemLab per hash
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
    void run(`from chemlab.${t} import SPEC\nresult = {k: dict(v) for k, v in SPEC.items()}`, { mode: 'chemlab' }).then((r) => {
      if (!live) return
      if (!r.ok) return setLoadErr(r.error)
      const s = r.result as Record<string, Spec>
      setVals(Object.fromEntries(Object.entries(s).map(([k, sp]) => { const p = q.get(k); return [k, p !== null && !check(sp, p) ? p : String(sp.default)] })))
      setSpec(s)
    })
    return () => { live = false }
  }, [tries, t])

  const names = spec ? Object.keys(spec) : []
  const errs = Object.fromEntries(names.map((k) => [k, check(spec![k], vals[k] ?? '')]).filter(([, e]) => e))
  const body = spec && !Object.keys(errs).length ? JSON.stringify(Object.fromEntries(names.map((k) => [k, num(vals[k])]))) : ''

  useEffect(() => {
    if (!body) return // out-of-range input: do not run
    const h = setTimeout(() => {
      void run(`from chemlab.${t} import run\nresult = run(${body})`, { mode: 'chemlab', latestWins: true }).then((r) => {
        if (r.ok) { setFail(''); setOut(r.result as Out) } else if (r.error !== 'superseded') setFail(r.error)
      })
    }, 150)
    return () => clearTimeout(h)
  }, [body, t])

  const flow = useMemo(() => pfd(t), [t])
  // hooks stay above the early returns; each drawing comes from the template's own geometry and inputs
  const sheet = useMemo(() => {
    if (!out?.ok) return ''
    if (t === 'cstr') return cstrViews(out.geometry, out.inputs)
    if (t === 'mccabe') return columnViews({ ...out.geometry, n_trays: out.geometry.n_trays ?? 0, feed_tray: out.geometry.feed_tray ?? 1 }, out.inputs)
    // no geometry when a 1-2 shell-and-tube exchanger cannot do the duty (the template warns)
    if (t === 'hx' && out.geometry.n_tubes != null) return hxViews(out.geometry as HxGeometry, out.inputs)
    return ''
  }, [t, out])

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
  const gen = t === 'cstr' && out ? (x: number) => -out.inputs.dHr.value * out.inputs.v0.value * out.inputs.CA0.value * x : () => 0
  const lines = (s: Ser, nm = 'conversion'): Line[] =>
    (s.branches ?? [{ stable: true, start: 0, stop: s.x.length }]).map((b) => ({
      name: s.branches ? (b.stable ? 'stable' : 'unstable') : nm,
      x: s.x.slice(b.start, b.stop), y: s.y.slice(b.start, b.stop), color: b.stable ? 'var(--primary)' : 'var(--destructive)', dash: !b.stable,
    }))
  const sr = out?.series ?? {}
  const flowsheet = flow && (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-base font-semibold">Process flow diagram</h2>
      {/* pfd() escapes all text and every other interpolated value is a number; no process values are drawn */}
      <div className="mt-2 rounded-md bg-white [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: flow }} />
      <Button className="mt-3 min-h-11" aria-label="Download SVG of the process flow diagram" onClick={() => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(new Blob([flow], { type: 'image/svg+xml' }))
        a.download = `${t === 'mccabe' ? 'column' : t}-pfd.svg`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href))
      }}>Download SVG</Button>
    </section>
  )
  const drawing = sheet && (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-base font-semibold">Drawing (2D, first-angle)</h2>
      {/* the drawing functions escape all text and every other interpolated value is a number */}
      <div className="mt-2 rounded-md bg-white [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: sheet }} />
      <Button className="mt-3 min-h-11" aria-label="Download SVG of the drawing" onClick={() => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(new Blob([sheet], { type: 'image/svg+xml' }))
        a.download = `${t === 'mccabe' ? 'column' : t}-drawing.svg`; a.click(); setTimeout(() => URL.revokeObjectURL(a.href)) // Safari/Firefox: revoke after the click is handled
      }}>Download SVG</Button>
    </section>
  )

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <h1 className="text-2xl font-semibold tracking-tight">ChemLab</h1>
      <p className="mt-1 text-sm text-muted-foreground">Reactor and distillation calculators. Runs on your device, no credits used.</p>
      <div aria-label="Template" className="mt-3 flex flex-wrap gap-2">
        {TABS.map(([n, l]) => (
          <button key={n} aria-pressed={n === t} onClick={() => { location.hash = `#chemlab/${n}` }}
            className={`min-h-11 min-w-11 rounded-lg border px-4 text-sm font-medium ${n === t ? 'border-primary bg-primary text-primary-foreground' : 'bg-card'}`}>{l}</button>
        ))}
      </div>
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
              {t === 'cstr' && SLIDERS.includes(k) && (
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
                  {out.geometry.height_m != null && <div><dt className="text-xs text-muted-foreground">D, H</dt><dd className="font-medium tabular-nums">{fmt(out.geometry.diameter_m)} m, {fmt(out.geometry.height_m)} m</dd></div>}
                </dl>
              </section>
              {t === 'cstr' && <>
              <fieldset className="rounded-lg border bg-card p-4">
                <legend className="px-1 text-base font-semibold">Steady states ({ss.length})</legend>
                {ss.map((s, i) => (
                  <label key={i} className="flex min-h-11 items-center gap-3 text-sm">
                    <input type="radio" name="state" className="size-5" checked={i === si} onChange={() => setSel(i)} />
                    <span>T = {fmt(s.T)} K, X = {fmt(s.X)} · <b className={s.stable ? 'text-primary' : 'text-destructive'}>{s.stable ? 'stable' : 'unstable'}</b></span>
                  </label>
                ))}
              </fieldset>
              {ss[si] && (
                <Suspense fallback={<p role="status" className="text-sm text-muted-foreground">Loading 3D view…</p>}>
                  <Cstr3D D={out.geometry.diameter_m} H={out.geometry.height_m} T={ss[si].T} T0={out.inputs.T0.value} Tmax={Math.max(...ss.map((s) => s.T))} UA={out.inputs.UA.value} />
                </Suspense>
              )}
              {drawing}
              {sr.heat_generated && sr.heat_removed && (
                <LineChart title="Heat generated and removed" xLabel="T (K)" yLabel="Heat (W)"
                  lines={[{ name: 'generated', x: sr.heat_generated.x, y: sr.heat_generated.y, color: 'var(--destructive)' }, { name: 'removed', x: sr.heat_removed.x, y: sr.heat_removed.y, color: 'var(--primary)' }]}
                  marks={ss.map((s, i) => ({ x: s.T, y: gen(s.X), color: 'currentColor', filled: s.stable, big: i === si }))} />
              )}
              {sr.s_curve && <LineChart title="S-curve: conversion vs residence time" logX xLabel="residence time (s)" yLabel="conversion X (-)" lines={lines(sr.s_curve)} />}
              </>}
              {flowsheet}
              {(CHARTS[t] ?? []).map(([k, title, xn, yn]) => sr[k] && (
                <LineChart key={k} title={title} xLabel={ax(xn, sr[k].x_unit)} yLabel={ax(yn, sr[k].y_unit)} lines={lines(sr[k], yn)} />
              ))}
              {t === 'mccabe' && sr.stages && <McCabe series={sr} stages={out.outputs.N_theoretical?.value} />}
              {t === 'mccabe' && drawing && (
                <Suspense fallback={<p role="status" className="text-sm text-muted-foreground">Loading 3D view…</p>}>
                  <Equip3D kind="column" g={{ ...out.geometry, n_trays: out.geometry.n_trays ?? 0, feed_tray: out.geometry.feed_tray ?? 1 }} />
                </Suspense>
              )}
              {t === 'mccabe' && (drawing || (
                <p className="text-sm text-muted-foreground">No column drawing: there are no real trays (the reboiler alone does the separation).</p>
              ))}
              {t === 'hx' && sr.hot_profile && sr.cold_profile && (
                <LineChart title="Counter-flow temperature profile" xLabel={ax('fraction of area from the hot inlet', sr.hot_profile.x_unit)} yLabel={ax('T', sr.hot_profile.y_unit)}
                  lines={[{ name: 'hot', x: sr.hot_profile.x, y: sr.hot_profile.y, color: 'var(--destructive)' }, { name: 'cold', x: sr.cold_profile.x, y: sr.cold_profile.y, color: 'var(--primary)' }]} />
              )}
              {t === 'hx' && drawing && (
                <Suspense fallback={<p role="status" className="text-sm text-muted-foreground">Loading 3D view…</p>}>
                  <Equip3D kind="hx" g={out.geometry as HxGeometry} />
                </Suspense>
              )}
              {t === 'hx' && drawing}
              {t === 'hx' && out.geometry.n_tubes == null && (
                <p className="text-sm text-muted-foreground">No exchanger drawing: a 1-2 shell-and-tube exchanger cannot do this duty (see the warning above).</p>
              )}
            </>
          )}
        </div>
      )}
    </main>
  )
}

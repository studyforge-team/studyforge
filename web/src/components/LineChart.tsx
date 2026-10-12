import { fmt } from '@/lib/fmt'
// Plain inline SVG line chart (no chart library). Several series, min/max ticks, optional steady-state marks.
export type Line = { name: string; x: (number | null)[]; y: (number | null)[]; color: string; dash?: boolean }
export type Mark = { x: number; y: number; color: string; filled: boolean; big?: boolean }

const W = 360, H = 230, L = 52, R = 12, T = 18, B = 40

export function LineChart({ title, lines, marks = [], xLabel, yLabel, logX }: { title: string; lines: Line[]; marks?: Mark[]; xLabel: string; yLabel: string; logX?: boolean }) {
  const tx = (x: number) => (logX ? Math.log10(x) : x) // logX: points with x <= 0 are dropped, tick labels stay in real units
  const pts = lines.map((s) => s.x.flatMap((x, i) => (x != null && (!logX || x > 0) && s.y[i] != null ? [[tx(x), s.y[i] as number]] : [])))
  const all = [...pts.flat(), ...marks.map((m) => [tx(m.x), m.y])]
  if (!all.length) return null
  const ext = (i: number) => [Math.min(...all.map((p) => p[i])), Math.max(...all.map((p) => p[i]))]
  const [x0, x1] = ext(0), [y0, y1] = ext(1)
  const sx = (x: number) => L + ((x - x0) / (x1 - x0 || 1)) * (W - L - R)
  const sy = (y: number) => H - B - ((y - y0) / (y1 - y0 || 1)) * (H - B - T)
  const names = [...new Map(lines.map((s) => [s.name, s])).values()]
  return (
    <figure className="rounded-lg border bg-card p-3">
      <figcaption className="text-sm font-medium">{title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={title} className="mt-1 w-full text-foreground" fontSize="11" fill="currentColor">
        <path d={`M${L} ${T}V${H - B}H${W - R}`} fill="none" stroke="currentColor" strokeOpacity=".4" />
        <text x={2} y={11}>{yLabel}</text>
        <text x={L - 4} y={sy(y1) + 4} textAnchor="end">{fmt(y1, 3)}</text>
        <text x={L - 4} y={sy(y0)} textAnchor="end">{fmt(y0, 3)}</text>
        <text x={L} y={H - B + 14} textAnchor="start">{fmt(logX ? 10 ** x0 : x0, 3)}</text>
        <text x={W - R} y={H - B + 14} textAnchor="end">{fmt(logX ? 10 ** x1 : x1, 3)}</text>
        <text x={(L + W - R) / 2} y={H - 6} textAnchor="middle">{xLabel}</text>
        {lines.map((s, i) => (
          <polyline key={i} points={pts[i].map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' ')} fill="none" strokeWidth="2" strokeDasharray={s.dash ? '5 3' : undefined} style={{ stroke: s.color }} />
        ))}
        {marks.map((m, i) => (
          <circle key={i} cx={sx(tx(m.x))} cy={sy(m.y)} r={m.big ? 7 : 5} strokeWidth="2" style={{ stroke: m.color, fill: m.filled ? m.color : 'var(--card)' }} />
        ))}
      </svg>
      <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground">
        {names.map((s) => <span key={s.name}><span aria-hidden="true" style={{ color: s.color }}>━ </span>{s.name}</span>)}
        {marks.length > 0 && <span>● stable, ○ unstable steady state</span>}
      </p>
    </figure>
  )
}

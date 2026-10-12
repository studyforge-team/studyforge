import { fmt } from '@/lib/fmt'
// Plain inline SVG McCabe-Thiele diagram (no chart library). x, y in 0..1; null points are dropped.
type Ser = { x: (number | null)[]; y: (number | null)[] }
const S = 400, L = 44, B = 36, P = 12, TICKS = [0, 0.2, 0.4, 0.6, 0.8, 1]
const sx = (x: number) => L + x * (S - L - P)
const sy = (y: number) => S - B - y * (S - B - P)
const LINES: [string, string, string, boolean][] = [ // [series key, legend, colour, dashed]
  ['diagonal', 'y = x', 'var(--muted-foreground)', true], ['equilibrium', 'equilibrium', 'var(--destructive)', false],
  ['q_line', 'q-line', 'var(--muted-foreground)', false], ['rectifying_line', 'rectifying', 'var(--primary)', false],
  ['stripping_line', 'stripping', 'var(--warn)', false], ['stages', 'stages', 'currentColor', false],
]

export function McCabe({ series, stages }: { series: Record<string, Ser>; stages?: number }) {
  const pts = (s?: Ser) => (s ? s.x.flatMap((x, i) => (x != null && s.y[i] != null ? [`${sx(x).toFixed(1)},${sy(s.y[i] as number).toFixed(1)}`] : [])).join(' ') : '')
  return (
    <figure className="rounded-lg border bg-card p-3">
      <figcaption className="text-sm font-medium">McCabe-Thiele diagram</figcaption>
      <svg viewBox={`0 0 ${S} ${S}`} role="img" aria-label={`McCabe-Thiele diagram${stages != null ? `, ${stages} theoretical stages` : ''}`} className="mx-auto mt-1 w-full max-w-[480px] text-foreground" fontSize="11" fill="currentColor">
        <path d={`M${L} ${P}V${S - B}H${S - P}`} fill="none" stroke="currentColor" strokeOpacity=".4" />
        {TICKS.map((t) => (
          <g key={t}>
            <text x={sx(t)} y={S - B + 14} textAnchor="middle">{fmt(t)}</text>
            <text x={L - 5} y={sy(t) + 4} textAnchor="end">{fmt(t)}</text>
          </g>
        ))}
        <text x={(L + S - P) / 2} y={S - 6} textAnchor="middle">x (light key, liquid)</text>
        <text transform={`translate(11 ${(P + S - B) / 2}) rotate(-90)`} textAnchor="middle">y (vapour)</text>
        {LINES.map(([k, , c, d]) => <polyline key={k} points={pts(series[k])} fill="none" strokeWidth="2" strokeDasharray={d ? '5 3' : undefined} style={{ stroke: c }} />)}
      </svg>
      <p className="mt-1 flex flex-wrap gap-x-4 text-xs text-muted-foreground">
        {LINES.map(([k, n, c]) => <span key={k}><span aria-hidden="true" style={{ color: c }}>━ </span>{n}</span>)}
      </p>
    </figure>
  )
}

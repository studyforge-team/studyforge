/**
 * LineChart — minimal SVG line chart for quiz attempt progress.
 *
 * Props:
 *   title  — chart heading
 *   lines  — array of { label, values: number[] }
 *   xLabel — x-axis label (e.g. "Attempt")
 *   yLabel — y-axis label (e.g. "%")
 */

type Line = { label: string; values: number[] }

export function LineChart({
  title,
  lines,
  xLabel,
  yLabel,
}: {
  title: string
  lines: Line[]
  xLabel?: string
  yLabel?: string
}) {
  if (!lines.length || !lines[0].values.length) return null

  const W = 320
  const H = 160
  const PAD = { top: 24, right: 16, bottom: 32, left: 40 }

  const allValues = lines.flatMap((l) => l.values)
  const minY = Math.min(0, ...allValues)
  const maxY = Math.max(100, ...allValues)
  const maxX = Math.max(...lines.map((l) => l.values.length)) - 1

  const scaleX = (i: number) =>
    maxX === 0
      ? PAD.left + (W - PAD.left - PAD.right) / 2
      : PAD.left + (i / maxX) * (W - PAD.left - PAD.right)

  const scaleY = (v: number) =>
    PAD.top + ((maxY - v) / (maxY - minY)) * (H - PAD.top - PAD.bottom)

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444']

  return (
    <figure className="my-2">
      <figcaption className="mb-1 text-xs font-semibold text-muted-foreground">{title}</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full overflow-visible rounded-lg border bg-card"
        aria-label={title}
        role="img"
      >
        {/* Y-axis grid lines */}
        {[0, 25, 50, 75, 100].map((pct) => {
          const y = scaleY(pct)
          return (
            <g key={pct}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke="#e5e7eb" strokeWidth={0.5} />
              <text x={PAD.left - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#6b7280">
                {pct}
              </text>
            </g>
          )
        })}

        {/* Lines */}
        {lines.map((line, li) => {
          const pts = line.values
            .map((v, i) => `${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`)
            .join(' ')
          return (
            <polyline
              key={li}
              points={pts}
              fill="none"
              stroke={COLORS[li % COLORS.length]}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )
        })}

        {/* Dots */}
        {lines.map((line, li) =>
          line.values.map((v, i) => (
            <circle
              key={`${li}-${i}`}
              cx={scaleX(i)}
              cy={scaleY(v)}
              r={3}
              fill={COLORS[li % COLORS.length]}
            >
              <title>{`${line.label}: ${v.toFixed(1)}%`}</title>
            </circle>
          )),
        )}

        {/* X-axis labels */}
        {lines[0].values.map((_, i) => (
          <text
            key={i}
            x={scaleX(i)}
            y={H - PAD.bottom + 14}
            textAnchor="middle"
            fontSize={9}
            fill="#6b7280"
          >
            {i + 1}
          </text>
        ))}

        {/* Axis labels */}
        {xLabel && (
          <text x={(W - PAD.left - PAD.right) / 2 + PAD.left} y={H - 2} textAnchor="middle" fontSize={9} fill="#6b7280">
            {xLabel}
          </text>
        )}
        {yLabel && (
          <text
            x={10}
            y={(H - PAD.top - PAD.bottom) / 2 + PAD.top}
            textAnchor="middle"
            fontSize={9}
            fill="#6b7280"
            transform={`rotate(-90, 10, ${(H - PAD.top - PAD.bottom) / 2 + PAD.top})`}
          >
            {yLabel}
          </text>
        )}
      </svg>
    </figure>
  )
}

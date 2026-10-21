export const fmt = (v: number | null | undefined, p = 4) => (v == null ? '—' : Math.abs(v) < 1e-9 ? '0' : String(Number(v.toPrecision(p))))

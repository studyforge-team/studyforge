export const fmt = (v: number | null | undefined, p = 4) => (v == null ? '—' : String(Number(v.toPrecision(p))))

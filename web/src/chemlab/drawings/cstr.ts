// CSTR general-arrangement sheet, first-angle projection, drawn from the template's own numbers.
// Same object as Cstr3D: flat-head cylinder, 4 baffles at 45/135/225/315 deg, feed nozzle at -x high,
// product nozzle at +x low, agitator shaft + flat-blade impeller d = D/3 at H/3, jacket only when UA > 0.
// World axes: x right in the front view, y up, z toward the viewer of the front view.
type Inputs = Record<string, { value: number; unit: string }>

let sheets = 0 // ponytail: module counter keeps ids unique per call; no randomness needed
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const n = (v: number) => +v.toFixed(1)
const mm = (m: number) => `${Math.round(m * 1000)} mm`
const sig = (v: number) => String(+v.toPrecision(4))

export function cstrViews(g: { diameter_m: number; height_m: number }, inputs: Inputs): string {
  const id = `cstr${++sheets}`
  const { diameter_m: D, height_m: H } = g
  const jacket = (inputs.UA?.value ?? 0) > 0
  const L = 0.8 * H // ponytail: liquid level fixed at 80 % of H (the 3D view fills the vessel)
  const dImp = D / 3
  // one scale from D and H so every view is proportional; fit the arrangement to the 1000 x 700 sheet
  const s = Math.min(613 / (2.62 * D), 560 / (1.2 * H + 1.12 * D))
  const r = (D * s) / 2, h = H * s, ri = (dImp * s) / 2
  const c = Math.SQRT1_2, w = 0.1 * D * s // baffle radial width
  const nr = 0.035 * D * s, stub = 0.25 * D * s // nozzle radius, stub length beyond shell
  const rj = 1.12 * r // jacket radius
  const xc = 117 + 0.75 * D * s, yT = 40 + 0.2 * h, yB = yT + h
  const xs = xc + 0.75 * D * s + 135 + 0.56 * D * s // side view axis
  const ly = (m: number) => yB - m * s
  const yIn = ly(0.88 * H), yOut = ly(0.12 * H), yImp = ly(H / 3), yL = ly(L)
  const yp = yB + 70 + rj // plan centre
  const A = `url(#${id}a)`
  const o: string[] = []
  const line = (x1: number, y1: number, x2: number, y2: number, cls = 'o') => o.push(`<line class="${cls}" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}"/>`)
  const rect = (x: number, y: number, W: number, Hh: number, cls = 'o') => o.push(`<rect class="${cls}" x="${n(x)}" y="${n(y)}" width="${n(W)}" height="${n(Hh)}"/>`)
  const circ = (x: number, y: number, R: number, cls = 'o') => o.push(`<circle class="${cls}" cx="${n(x)}" cy="${n(y)}" r="${n(R)}"/>`)
  const text = (x: number, y: number, t: string, anchor = 'start', rot = 0) =>
    o.push(`<text x="${n(x)}" y="${n(y)}" text-anchor="${anchor}"${rot ? ` transform="rotate(${rot} ${n(x)} ${n(y)})"` : ''}>${esc(t)}</text>`)
  // leader: label at the tail (x1,y1), arrowhead tip exactly on the part at (x2,y2)
  const lead = (x1: number, y1: number, x2: number, y2: number, t: string, anchor = 'start', ty = y1 + 3, tx = x1 + (anchor === 'start' ? 4 : 0)) => {
    o.push(`<line class="l" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}" marker-end="${A}"/>`)
    text(tx, ty, t, anchor)
  }
  // dimension lines with arrowheads on both extension lines
  const dimV = (x: number, y1: number, y2: number, xFrom: number, t: string) => {
    line(xFrom, y1, x - 4, y1, 'e'); line(xFrom, y2, x - 4, y2, 'e')
    o.push(`<line class="l" x1="${n(x)}" y1="${n(y1)}" x2="${n(x)}" y2="${n(y2)}" marker-start="${A}" marker-end="${A}"/>`)
    text(x - 4, (y1 + y2) / 2, t, 'middle', -90)
  }
  const dimH = (y: number, x1: number, x2: number, yFrom: number, t: string, ty = y - 4) => {
    line(x1, yFrom, x1, y + 4, 'e'); line(x2, yFrom, x2, y + 4, 'e')
    o.push(`<line class="l" x1="${n(x1)}" y1="${n(y)}" x2="${n(x2)}" y2="${n(y)}" marker-start="${A}" marker-end="${A}"/>`)
    text((x1 + x2) / 2, ty, t, 'middle')
  }
  const cap = (x: number, y: number, t: string) => o.push(`<text class="cap" x="${n(x)}" y="${n(y)}">${t}</text>`)

  // vessel body shared by the front (horizontal = x) and side (horizontal = z) views
  const body = (xa: number) => {
    rect(xa - r, yL, 2 * r, yB - yL, 'liq')
    rect(xa - c * r, yL, c * w, yB - yL, 'baf'); rect(xa + c * (r - w), yL, c * w, yB - yL, 'baf')
    if (jacket) rect(xa - rj, ly(0.8 * H), 2 * rj, 0.8 * h, 'o')
    rect(xa - r, yT, 2 * r, h, 'o2')
    rect(xa - 2, yT - 0.1 * h, 4, 0.1 * h + (yImp - yT), 'sh') // shaft, motor to impeller
    rect(xa - ri, yImp - 3, 2 * ri, 6, 'imp')
    rect(xa - 0.12 * D * s, yT - 0.2 * h, 0.24 * D * s, 0.1 * h, 'mot')
  }

  // ---- front elevation
  cap(40, 28, 'FRONT ELEVATION')
  body(xc)
  rect(xc - r - stub, yIn - nr, stub, 2 * nr, 'noz') // feed, -x
  rect(xc + r, yOut - nr, stub, 2 * nr, 'noz') // product, +x
  const xTip = xc + r + stub
  dimV(xc - 0.75 * D * s - 35, yT, yB, xc - r, `H = ${mm(H)}`)
  dimV(xc - 0.75 * D * s - 62, yL, yB, xc - r, `Liquid level = ${mm(L)}`)
  dimH(yB + 30, xc - r, xc + r, yB, `D = ${mm(D)}`)
  dimH(yImp + 16, xc - ri, xc + ri, yImp + 3, `d = D/3 = ${mm(dImp)}`, yImp + 28)
  const xl = xTip + 15
  lead(xl, yT - 0.15 * h, xc + 0.12 * D * s, yT - 0.15 * h, 'Motor')
  lead(xl, yT - 0.05 * h, xc + 2, yT - 0.05 * h, 'Shaft')
  if (jacket) lead(xl, ly(0.65 * H), xc + rj, ly(0.65 * H), 'Jacket')
  lead(xl, ly(0.45 * H), xc + c * (r - w / 2), ly(0.45 * H), 'Baffle (4 off)')
  lead(xl, yImp, xc + ri, yImp, 'Impeller')
  lead(xl, yOut, xTip, yOut, 'Product out')
  lead(xc - r - stub / 2, yIn + 2 * nr + 22, xc - r - stub / 2, yIn + nr, 'Feed in', 'middle', yIn + 2 * nr + 34)

  // ---- left-hand side view, to the right of the front elevation (first angle)
  cap(xs - 0.56 * D * s, 28, 'LEFT-HAND SIDE VIEW')
  body(xs)
  circ(xs, yIn, 1.6 * nr, 'noz'); circ(xs, yIn, nr, 'noz') // feed nozzle seen end-on
  circ(xs, yOut, nr, 'hid') // product nozzle is behind the shell: hidden
  const xr = xs + 0.56 * D * s + 25
  if (jacket) lead(xr, ly(0.65 * H), xs + rj, ly(0.65 * H), 'Jacket')
  lead(xr, yIn, xs + 1.6 * nr, yIn, 'Feed in')
  lead(xr, ly(0.45 * H), xs + c * (r - w / 2), ly(0.45 * H), 'Baffle (4 off)')
  lead(xr, yImp, xs + ri, yImp, 'Impeller')
  lead(xr, yOut, xs + nr, yOut, 'Product out')

  // ---- plan, below the front elevation on the same axis
  cap(40, yp - rj, 'PLAN')
  if (jacket) circ(xc, yp, rj)
  circ(xc, yp, r, 'o2')
  for (const a of [45, 135, 225, 315]) o.push(`<rect class="baf" x="${n(xc + r - w)}" y="${n(yp - 1.5)}" width="${n(w)}" height="3" transform="rotate(${a} ${n(xc)} ${n(yp)})"/>`)
  rect(xc - r - stub, yp - nr, stub, 2 * nr, 'noz'); rect(xc + r, yp - nr, stub, 2 * nr, 'noz')
  circ(xc, yp, ri, 'hid'); line(xc - ri, yp, xc + ri, yp, 'hid'); line(xc, yp - ri, xc, yp + ri, 'hid')
  rect(xc - 0.12 * D * s, yp - 0.12 * D * s, 0.24 * D * s, 0.24 * D * s, 'mot') // motor on top is visible in plan; shaft is under it
  lead(xc - r - stub / 2, yp - 32, xc - r - stub / 2, yp - nr, 'Feed in', 'end', yp - 29, xc - r - stub / 2 - 6)
  lead(xc + r + stub / 2, yp + 32, xc + r + stub / 2, yp + nr, 'Product out', 'start', yp + 44, xc + r + stub / 2 + 6)
  const ab = c * (r - w / 2)
  lead(xc + rj * 0.9 + 30, yp + rj * 0.9 + 30, xc + ab, yp + ab, 'Baffle (4 off)')
  const ia = (-80 * Math.PI) / 180
  lead(xc + 18, yp - rj - 12, xc + ri * Math.cos(ia), yp + ri * Math.sin(ia), 'Impeller / shaft (hidden)', 'start', yp - rj - 15, xc + 22)
  if (jacket) lead(xc - 0.8 * rj - 70, yp + 0.6 * rj + 30, xc - 0.8 * rj, yp + 0.6 * rj, 'Jacket', 'end')

  const rows = Object.entries(inputs)
  // ---- first-angle projection symbol (IS SP 46): truncated cone, elevation left, left-hand view right
  const sx = 672, sy = 685 - (74 + rows.length * 14 + 8) - 40
  o.push(`<g class="sym"><path d="M${sx} ${sy - 10}H${sx + 34}L${sx + 40} ${sy - 18}V${sy + 18}L${sx + 34} ${sy + 10}H${sx}Z"/>`)
  o.push(`<line class="e" x1="${sx - 6}" y1="${sy}" x2="${sx + 52}" y2="${sy}"/>`)
  o.push(`<circle cx="${sx + 82}" cy="${sy}" r="18"/><circle cx="${sx + 82}" cy="${sy}" r="10"/></g>`)
  text(sx + 108, sy + 4, 'FIRST ANGLE PROJECTION')

  // ---- title block
  const bh = 74 + rows.length * 14 + 8
  const bx = 640, by = 685 - bh
  rect(bx, by, 340, bh, 'tb')
  line(bx, by + 26, bx + 340, by + 26, 'e')
  text(bx + 8, by + 17, 'CSTR — general arrangement (schematic, not to scale)')
  text(bx + 8, by + 42, `Vessel drawn at approx. 1:${Math.round(1000 / s)}; fittings schematic. Liquid level 0.8 H.`)
  text(bx + 8, by + 56, `Dimensions in mm. D = ${mm(D)}, H = ${mm(H)}; dashed = hidden.`)
  text(bx + 8, by + 70, 'Template inputs:')
  rows.forEach(([k, v], i) => text(bx + 8, by + 86 + i * 14, `${k} = ${sig(v.value)} ${v.unit}`))

  const title = `CSTR general arrangement, D ${mm(D)}, H ${mm(H)}`
  const desc = 'Schematic first-angle projection of a stirred tank reactor: front elevation, plan below it and left-hand side view to its right, with a title block listing the template inputs.'
  const b = `#${id}b`
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" role="img" aria-labelledby="${id}t ${id}d">
<title id="${id}t">${esc(title)}</title><desc id="${id}d">${esc(desc)}</desc>
<defs><marker id="${id}a" viewBox="0 0 8 6" refX="8" refY="3" markerWidth="8" markerHeight="6" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L8 3L0 6Z" fill="#111"/></marker>
<style>${b} .o,${b} .o2,${b} .noz,${b} .mot,${b} .tb,${b} .sym *,${b} .sym{fill:none;stroke:#111;stroke-width:1}${b} .o2{stroke-width:2}${b} .noz{fill:#fff;stroke-width:1.5}${b} .mot,${b} .imp{fill:#cbd5e1}${b} .imp,${b} .sh{fill:#555;stroke:#111}${b} .liq{fill:#dbeafe;stroke:none}${b} .baf{fill:#94a3b8;stroke:#111;stroke-width:.8}${b} .hid{fill:none;stroke:#111;stroke-dasharray:5 3}${b} .l,${b} .e{stroke:#111;stroke-width:.7;fill:none}${b} text{font:11px Arial,sans-serif;fill:#111;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}${b} .cap{font-weight:700;font-size:12px}</style></defs>
<g id="${id}b"><rect width="1000" height="700" fill="#fff"/><rect class="o2" x="10" y="10" width="980" height="680" fill="none"/>
${o.join('\n')}
</g></svg>
`
}

// Tubular reactor (PFR) general arrangement (V2Db), first-angle, drawn from the pfr template's geometry:
// tube inner diameter, length (4V / pi D^2) and volume. Front elevation: straight jacket-less tube with flanged
// inlet and outlet nozzles and flow arrows; a long tube is drawn with two conventional break lines and
// dimensioned at its true length. Section A-A: the tube bore with a schematic wall. The template has no wall
// thickness, flange or nozzle size, so those are schematic and not dimensioned.
import { mm, n as r1, scaleText, sheet, sig, type Inputs } from './sheet.ts'

export type PfrGeometry = { length_m: number; diameter_m: number; volume_m3: number }

const BREAK_RATIO = 12 // L/D above this: drawn broken (shorter ratios keep true proportions)

export function pfrViews(g: PfrGeometry, inputs: Inputs): string {
  const L = g.length_m, D = g.diameter_m, V = g.volume_m3
  if (![L, D, V].every((v) => Number.isFinite(v) && v > 0)) return ''
  const S = sheet('pfr')
  const { rect, line, path, text, cap, lead, arrow, dimH, circ } = S
  const broken = L / D > BREAK_RATIO

  // ---- front elevation: tube (xa..xb) on a horizontal axis at yc, flanges at both ends, nozzle stubs beyond
  const s = broken ? 0 : Math.min(520 / L, 110 / D) // px per m, only when drawn to scale
  const Lp = broken ? 520 : L * s
  const hd = broken ? 40 : D * s
  const xa = 500 - Lp / 2, xb = 500 + Lp / 2, yc = 150
  const y0 = yc - hd / 2, y1 = yc + hd / 2
  const fh = hd + 16, ns = Math.max(6, 0.5 * hd) // flange height, nozzle stub bore
  cap(40, 28, 'FRONT ELEVATION')
  if (broken) {
    const g2 = 12, b1 = xa + 0.3 * Lp, b2 = b1 + g2 + 60 // two breaks, a short stub of tube between them
    const sCurve = (x: number) => `M${r1(x)} ${r1(y0)}C${r1(x + 7)} ${r1(yc - hd / 4)} ${r1(x - 7)} ${r1(yc + hd / 4)} ${r1(x)} ${r1(y1)}`
    const seg = (x1: number, x2: number) => { line(x1, y0, x2, y0, 'o2'); line(x1, y1, x2, y1, 'o2') }
    seg(xa, b1); seg(b1 + g2, b2); seg(b2 + g2, xb)
    for (const x of [b1, b1 + g2, b2, b2 + g2]) path(sCurve(x), 'o2')
  } else {
    rect(xa, y0, Lp, hd, 'o2')
  }
  line(xa - 34, yc, xb + 34, yc, 'cl')
  for (const [xf, d] of [[xa, -1], [xb, 1]] as const) {
    rect(xf - 4, yc - fh / 2, 8, fh, 'noz') // tube flange
    rect(xf + d * 4 - (d < 0 ? 30 : 0), yc - ns / 2, 30, ns, 'noz') // nozzle stub
    rect(xf + d * 34 - (d < 0 ? 5 : 0), yc - ns / 2 - 5, 5, ns + 10, 'noz') // nozzle flange
  }
  arrow(xa - 40 - 62, yc, xa - 40, yc)
  arrow(xb + 40, yc, xb + 40 + 62, yc)
  text(xa - 40 - 31, yc - 10, 'Feed in', 'middle')
  text(xb + 40 + 31, yc - 10, 'Product out', 'middle')
  lead(xa - 70, y1 + 34, xa - 22, yc + ns / 2, 'Flanged nozzle', 'end')
  lead(xb + 70, y1 + 34, xb + 22, yc + ns / 2, 'Flanged nozzle')
  const dimT = `L = ${sig(L)} m${broken ? ' (broken, true length)' : ''}`
  dimH(y1 + 78, xa, xb, y1 + 8, dimT)
  // cutting plane A-A across the tube (in the stub between the breaks when broken), looking toward the inlet (-x)
  const xcut = broken ? xa + 0.3 * Lp + 12 + 30 : xa + 0.55 * Lp
  line(xcut, yc - hd / 2 - 18, xcut, yc + hd / 2 + 18, 'cl')
  for (const ye of [yc - hd / 2 - 18, yc + hd / 2 + 18]) { arrow(xcut, ye, xcut - 14, ye); text(xcut + 4, ye + (ye < yc ? -2 : 10), 'A') }

  // ---- section A-A: bore at true size for its own scale, wall a schematic ring
  const R = 110, wall = 14, cx = 300, cy = 520
  const k = R / (D / 2) // px per m in this view
  cap(40, 340, `SECTION A–A (TUBE BORE, ${scaleText(k)})`)
  const ring = (r: number) => `M${r1(cx - r)} ${r1(cy)}a${r1(r)} ${r1(r)} 0 1 0 ${r1(2 * r)} 0a${r1(r)} ${r1(r)} 0 1 0 ${r1(-2 * r)} 0Z`
  S.o.push(`<path class="cut" fill-rule="evenodd" d="${ring(R + wall)}${ring(R)}"/>`)
  circ(cx, cy, R, 'o2')
  line(cx - R - wall - 14, cy, cx + R + wall + 14, cy, 'cl')
  line(cx, cy - R - wall - 14, cx, cy + R + wall + 14, 'cl')
  arrow(cx - 4, cy, cx - R, cy)
  arrow(cx + 4, cy, cx + R, cy)
  text(cx, cy - 8, `Ø D = ${mm(D)}`, 'middle')
  lead(cx + R + 40, cy - R - wall + 10, cx + 0.7071 * (R + wall / 2), cy - 0.7071 * (R + wall / 2), 'Wall (schematic)')

  const notes = [
    `Tube inner diameter D = ${mm(D)}.`,
    `Length L = ${sig(L)} m.`,
    `V = ${sig(V)} m³.`,
    broken ? 'Length broken: not to scale.' : `Elevation approx. ${scaleText(s)} at 1000 mm sheet width.`,
    `Section A–A ${scaleText(k)}. Wall not to scale.`,
    'Flanges and nozzles schematic.',
  ]
  if (broken) notes.push('Tube diameter drawn enlarged in elevation.')
  S.titleBlock('Tubular reactor (PFR)', notes, inputs)
  return S.finish(
    `Tubular reactor (PFR), ${mm(D)} bore, ${sig(L)} m long, volume ${sig(V)} m³`,
    `Schematic first-angle drawing of a straight tubular reactor: front elevation with flanged inlet and outlet nozzles and flow arrows${broken ? ', the tube drawn with break lines and dimensioned at its true length' : ''}, and section A-A through the tube bore, with a title block listing the template inputs.`,
  )
}

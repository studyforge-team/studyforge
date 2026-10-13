// Shell-and-tube heat exchanger general arrangement (V2Db), first-angle, drawn from the hx template's geometry:
// 1 shell pass, 2 tube passes, tube count, tube OD, tube length, triangular pitch, bundle and shell diameter.
// Front elevation: shell between two tube sheets, front channel with a pass partition, rear return bonnet,
// typical tubes, tube-side and shell-side nozzles. Section C-C: the tube sheet with exactly n_tubes tubes on the
// template's pitch, split into the two passes. Heads, nozzles and the partition lane are schematic; the template
// does not size baffles or decide which fluid goes in the shell, so neither is drawn or labelled.
import { mm, n as r1, scaleText, sheet, type Inputs } from './sheet.ts'

export type HxGeometry = {
  n_tubes: number; tube_od_m: number; tube_length_m: number; pitch_m: number
  bundle_diameter_m: number; shell_diameter_m: number; tube_passes?: number; shell_passes?: number
}

const MAX_TUBES_DRAWN = 400 // more than this: the tube field is drawn as an outline and the count written

// Triangular-pitch tube positions (centre to centre = pitch), two passes split by a horizontal lane one pitch wide:
// the n positions nearest the centre, half above the lane and half mirrored below. The lattice is tried at three
// horizontal offsets and the most compact kept, so the tubes stay inside the template's bundle diameter
// (checked in tests for every even n up to MAX_TUBES_DRAWN). Units: metres from the shell axis.
export function tubeLayout(n: number, pitch: number): [number, number][] {
  const half = Math.ceil(n / 2)
  const rowH = pitch * Math.sqrt(3) / 2
  const R = pitch * (Math.sqrt(half) + 3) // generous search radius
  const reach = (pts: [number, number][]) => Math.max(...pts.map(([x, y]) => Math.hypot(x, y)))
  let best: [number, number][] = []
  for (const shift of [0, 0.25, 0.5]) {
    const pts: [number, number][] = []
    for (let j = 0; j * rowH <= R + rowH; j++) {
      const y = pitch / 2 + j * rowH // first row half a pitch from the lane centre line
      for (let i = -Math.ceil(R / pitch) - 2; i <= Math.ceil(R / pitch) + 2; i++)
        pts.push([(i + shift) * pitch + (j % 2 ? pitch / 2 : 0), y])
    }
    pts.sort((a, b) => Math.hypot(...a) - Math.hypot(...b) || a[0] - b[0])
    const top = pts.slice(0, half)
    const all = [...top, ...top.slice(0, n - half).map(([x, y]): [number, number] => [x, -y])]
    if (!best.length || reach(all) < reach(best) - 1e-12) best = all
  }
  return best
}

export function hxViews(g: HxGeometry, inputs: Inputs): string {
  const n = Math.round(g.n_tubes), Lt = g.tube_length_m, Ds = g.shell_diameter_m, Db = g.bundle_diameter_m
  const dto = g.tube_od_m, p = g.pitch_m
  if (!(n >= 1) || !(Lt > 0) || !(Ds > 0) || !(Db > 0) || !(dto > 0) || !(p >= dto)) return ''
  const S = sheet('hx')
  const { rect, line, path, text, cap, lead, dimH, circ } = S

  // ---- front elevation, horizontal: channel (0.5 Ds) + tube length + return bonnet (0.25 Ds deep), schematic heads
  const s = Math.min(640 / (Lt + 0.75 * Ds), 110 / Ds)
  const ex = Ds * s < 38 ? 40 / (Ds * s) : 1 // very thin shells drawn taller (always by ×1.05 or more), and the sheet says so
  const exL = Lt * s < 114 ? 120 / (Lt * s) : 1 // very short shells drawn longer so nozzles and labels fit, ditto
  const hs = Ds * s * ex, ch = 0.5 * Ds * s * ex, bon = 0.25 * Ds * s * ex, L = Lt * s * exL
  const xa = 470 - (ch + L + bon) / 2 // channel flange
  const xt1 = xa + ch, xt2 = xt1 + L // tube sheets
  const yc = 175, y0 = yc - hs / 2, y1 = yc + hs / 2
  const toPx = hs / Ds // across the shell: px per m
  cap(40, 28, 'FRONT ELEVATION')
  rect(xt1, y0, L, hs, 'o2') // shell
  rect(xa, y0, ch, hs, 'o2') // front channel
  line(xa, yc, xt1, yc, 'o2') // pass partition: tube-side in below, out above
  path(`M${r1(xt2)} ${r1(y0)}A${r1(bon)} ${r1(hs / 2)} 0 0 1 ${r1(xt2)} ${r1(y1)}`, 'o2') // rear return bonnet
  rect(xt1 - 2, y0 - 4, 4, hs + 8, 'cut'); rect(xt2 - 2, y0 - 4, 4, hs + 8, 'cut') // tube sheets
  line(xa - 20, yc, xt2 + bon + 20, yc, 'cl')
  // typical tubes (hidden behind the shell): the same rows as section C-C, nearest the lane to the bundle edge
  const inner = (p / 2) * toPx, outer = Math.max(inner, (Db / 2 - dto / 2) * toPx)
  const m = Math.max(1, Math.min(3, Math.round(hs / 36)))
  for (let i = 0; i < m; i++) {
    const d = m === 1 ? inner : inner + ((outer - inner) * i) / (m - 1)
    for (const y of [yc - d, yc + d]) line(xt1, y, xt2, y, 'hid')
  }
  const nz = Math.max(6, 0.12 * hs), st = 18
  const off = Math.max(0.12 * L, nz / 2 + 6) // shell nozzles clear of the tube sheets
  rect(xa + ch / 2 - nz / 2, y1, nz, st, 'noz') // tube side in (bottom half of the channel)
  rect(xa + ch / 2 - nz / 2, y0 - st, nz, st, 'noz') // tube side out (top half)
  rect(xt1 + off - nz / 2, y0 - st, nz, st, 'noz') // shell side, near the front tube sheet
  rect(xt2 - off - nz / 2, y1, nz, st, 'noz') // shell side, near the rear tube sheet
  lead(xa - 30, y0 - st - 12, xa + ch / 2, y0 - st, 'Tube side out', 'end')
  lead(xa - 30, y1 + st + 14, xa + ch / 2, y1 + st, 'Tube side in', 'end')
  lead(xa - 30, yc - 14, xa + 0.3 * ch, yc, 'Pass partition', 'end')
  lead(xt1 + off + 40, y0 - st - 24, xt1 + off, y0 - st, 'Shell side nozzle')
  lead(xt2 - off + 40, y1 + st + 24, xt2 - off, y1 + st, 'Shell side nozzle')
  lead(xt2 + bon + 40, y0 - 10, xt2 + bon * 0.8, yc - hs * 0.3, 'Return bonnet')
  lead(xt2 + bon + 40, y1 + 10, xt2, y1 - 2, 'Tube sheet')
  const dimT = `Tube length = ${mm(Lt)}${exL > 1 ? ' (not to scale)' : ''}`
  dimH(y1 + st + 52, xt1, xt2, y1, dimT, L < dimT.length * 6 + 16) // text beside a short dimension, not on it
  // cutting plane C-C across the middle of the shell, looking toward the front tube sheet (-x)
  const xcut = xt1 + 0.5 * L
  line(xcut, y0 - 18, xcut, y1 + 18, 'cl')
  for (const ye of [y0 - 18, y1 + 18]) { S.arrow(xcut, ye, xcut - 14, ye); text(xcut + 4, ye + (ye < yc ? -2 : 10), 'C') }

  // ---- section C-C through the shell and the tube bundle: every tube on the template's pitch
  const R = 150, cx = 300, cy = 500, wall = 5 // shell wall thickness schematic
  const k = R / (Ds / 2) // px per m in this view
  cap(40, 330, `SECTION C–C (TUBE BUNDLE, ${n} TUBES, ${scaleText(k)})`)
  const ring = (r: number) => `M${r1(cx - r)} ${r1(cy)}a${r1(r)} ${r1(r)} 0 1 0 ${r1(2 * r)} 0a${r1(r)} ${r1(r)} 0 1 0 ${r1(-2 * r)} 0Z`
  S.o.push(`<path class="cut" fill-rule="evenodd" d="${ring(R + wall)}${ring(R)}"/>`) // cut shell wall, hatched
  circ(cx, cy, (Db / 2) * k, 'hid') // bundle limit from the template's bundle diameter
  line(cx - R, cy, cx + R, cy, 'cl')
  if (n <= MAX_TUBES_DRAWN) {
    for (const [x, y] of tubeLayout(n, p)) circ(cx + x * k, cy - y * k, Math.max(0.6, (dto / 2) * k), 'tube')
  } else {
    text(cx, cy - 12, `${n} tubes (not drawn singly)`, 'middle') // the dashed bundle limit outlines the tube field
  }
  lead(cx + R + 40, cy - R + 10, cx + 0.7071 * R, cy - 0.7071 * R, `Shell ID ${mm(Ds)}`)
  lead(cx + R + 40, cy - R + 34, cx + (Db / 2) * k * 0.6, cy - (Db / 2) * k * 0.8, `Bundle ${mm(Db)} (dashed)`)
  lead(cx + R + 40, cy + 6, cx + R * 0.98, cy, 'Pass partition lane')
  lead(cx - R - 40, cy - R * 0.6, cx - 0.3 * (Db / 2) * k, cy - 0.5 * (Db / 2) * k, 'Pass 2 (out)', 'end')
  lead(cx - R - 40, cy + R * 0.6, cx - 0.3 * (Db / 2) * k, cy + 0.5 * (Db / 2) * k, 'Pass 1 (in)', 'end')

  const xf = (v: number) => (v < 10 ? String(+v.toFixed(2)) : String(Math.round(v))) // never rounds a stretch to ×1
  const notes = [
    `${n} tubes, ${mm(dto)} OD, ${mm(Lt)} long.`,
    `Triangular pitch ${mm(p)}; 1 shell, 2 tube passes.`,
    `Bundle ${mm(Db)}, shell ID ${mm(Ds)}.`,
    `Elevation approx. ${scaleText(s)} at 1000 mm sheet width.`,
    'Heads, nozzles, tube sheets, shell wall schematic.',
    'Baffles and fluid sides not set by the template.',
  ]
  if (ex > 1) notes.push(`Shell height drawn ×${xf(ex)}.`)
  if (exL > 1) notes.push(`Tube length drawn ×${xf(exL)}.`)
  S.titleBlock('Shell-and-tube heat exchanger — general arrangement', notes, inputs)
  return S.finish(
    `Shell-and-tube heat exchanger, ${n} tubes, shell ${mm(Ds)}, tube length ${mm(Lt)}`,
    `Schematic first-angle drawing of a one-shell-pass, two-tube-pass exchanger: front elevation with channel, pass partition, tube sheets, return bonnet and nozzles, and section C-C through the bundle showing ${n} tubes on a triangular pitch inside the bundle limit, with a title block listing the template inputs.`,
  )
}

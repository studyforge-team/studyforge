// Distillation column general arrangement (V2Db), first-angle, drawn from the McCabe-Thiele template's
// geometry: diameter, tangent height (real trays x tray spacing), number of real trays and the feed tray.
// Front elevation with 2:1 heads, trays with alternating downcomers (single-pass cross flow), the feed tray in
// red, five nozzles; section B-B shows one tray deck. Heads, nozzles and the tray layout are schematic: the
// template sizes only D and H. Tray 1 is the top tray.
import { mm, scaleText, sheet, type Inputs } from './sheet.ts'

export type ColumnGeometry = { diameter_m: number; height_m: number; n_trays: number; feed_tray: number }

const MIN_W = 26 // px: a thinner column is drawn wider and the sheet says by how much
const MIN_TRAY_GAP = 5 // px: closer trays are thinned out (every k-th drawn) and the sheet says so

export function columnViews(g: ColumnGeometry, inputs: Inputs): string {
  const { diameter_m: D, height_m: H } = g
  const nT = Math.round(g.n_trays)
  // no trays: the reboiler alone does the separation (the page says so); non-finite input draws nothing
  if (!(nT >= 1) || !Number.isFinite(H) || !(H > 0) || !Number.isFinite(D) || !(D > 0) || !Number.isFinite(g.feed_tray)) return ''
  const f = Math.min(nT, Math.max(1, Math.round(g.feed_tray)))
  const S = sheet('col')
  const { rect, line, path, text, cap, lead, arrow, dimV, dimH, circ } = S

  // ---- scales: one vertical scale for the elevation; the width is exaggerated only when it would vanish
  const sv = Math.min(500 / (H + D / 2), 260 / D)
  const ex = D * sv < MIN_W ? MIN_W / (D * sv) : 1
  const w = D * sv * ex, hd = Math.max(3, (D / 4) * sv), hp = H * sv
  const xc = 300, x0 = xc - w / 2, x1 = xc + w / 2
  const yT = 70 + hd, yB = yT + hp
  const sp = hp / nT // px between trays
  const k = Math.max(1, Math.ceil(MIN_TRAY_GAP / sp))
  const yTray = (i: number) => yT + (i - 0.5) * sp
  const yFeed = yTray(f) - Math.min(0.3 * sp, 6)
  // cutting plane B-B just above a tray in the upper third, kept at least 14 px from the feed nozzle (its B
  // letters sit beside the nozzle stub); the feed label then goes on the far side of the plane
  const ybOf = (i: number) => yTray(i) - (i === f ? 0.4 * sp : Math.min(0.4 * sp, 8))
  let m = Math.max(1, Math.min(nT, Math.round(nT / 3) + 1))
  if (Math.abs(ybOf(m) - yFeed) < 14) {
    const step = Math.ceil(14 / sp) + 1
    m = f - step >= 1 ? f - step : f + step <= nT ? f + step : f
  }
  const yb = ybOf(m) // with one tray the plane sits 0.4 spacing above it, well clear of the feed nozzle
  const downcomers = k === 1 && sp >= 8

  // ---- front elevation
  cap(40, 28, 'FRONT ELEVATION')
  rect(x0, yT, w, hp, 'liq')
  path(`M${x0} ${yT}L${x0} ${yB}A${w / 2} ${hd} 0 0 0 ${x1} ${yB}L${x1} ${yT}A${w / 2} ${hd} 0 0 0 ${x0} ${yT}Z`, 'o2')
  line(xc, yT - hd - 30, xc, yB + hd + 30, 'cl')
  for (let i = 1; i <= nT; i++) {
    if ((i - 1) % k !== 0 && i !== nT && i !== f && i !== m) continue // feed, last and section tray always drawn
    const y = yTray(i)
    line(x0, y, x1, y, i === f ? 'feed' : 'tray')
    if (downcomers) { // the last tray's downcomer drops into the sump
      const xd = i % 2 ? x1 - 0.2 * w : x0 + 0.2 * w // downcomer alternates sides: liquid crosses each tray
      line(xd, y, xd, y + 0.75 * sp)
    }
  }
  const stub = 22, nh = 4
  const yRef = yT + Math.max(2, 0.25 * sp), yReb = yB - Math.max(2, 0.25 * sp)
  rect(xc - nh, yT - hd - stub, 2 * nh, stub, 'noz') // vapour to condenser
  rect(xc - nh, yB + hd, 2 * nh, stub, 'noz') // bottoms
  rect(x1, yRef - nh, stub, 2 * nh, 'noz') // reflux
  rect(x1, yReb - nh, stub, 2 * nh, 'noz') // reboiler vapour return
  rect(x0 - stub, yFeed - nh, stub, 2 * nh, 'noz') // feed
  dimV(x0 - 140, yT, yB, x0, `H = ${mm(H)} (tangent to tangent)`)
  dimH(yB + hd + 40, x0, x1, yB, ex > 1 ? `D = ${mm(D)} (width drawn ×${ex < 10 ? ex.toFixed(1) : Math.round(ex)})` : `D = ${mm(D)}`, true)

  // right-hand labels, pushed apart so none overlap; leaders slant when a label had to move
  const xl = x1 + 60
  const labels: [number, number, number, string][] = [
    [yT - hd - 16, xc + nh, yT - hd - 16, 'Vapour to condenser'],
    [yRef, x1 + stub, yRef, 'Reflux in'],
    [yTray(1), x1, yTray(1), 'Tray 1 (top)'],
    [yTray(nT), x1, yTray(nT), `Tray ${nT} (bottom)`],
    [yReb, x1 + stub, yReb, 'Reboiler vapour in'],
    [yB + hd + 12, xc + nh, yB + hd + 12, 'Bottoms out'],
  ]
  if (nT === 1) labels.splice(3, 1)
  let prev = -Infinity
  for (const L of labels) { L[0] = Math.max(L[0], prev + 16); prev = L[0] }
  for (let i = labels.length - 1, next = 640; i >= 0; i--) { labels[i][0] = Math.min(labels[i][0], next - 16); next = labels[i][0] }
  for (const [y, tx, ty, t] of labels) lead(xl, y, tx, ty, t)

  // feed label on the far side of the cutting plane, and never on the H extension lines at yT / yB
  let yfl = yFeed + (yb < yFeed ? 26 : -28)
  if (Math.abs(yfl - yT) < 10 || Math.abs(yfl - yB) < 10) yfl = yFeed + (yfl > yFeed ? -28 : 26)
  lead(x0 - 30, yfl, x0 - stub, yFeed, `Feed (tray ${f})`, 'end')
  line(x0 - 18, yb, x1 + 18, yb, 'cl')
  for (const xe of [x0 - 18, x1 + 18]) { arrow(xe, yb, xe, yb + 14); text(xe + (xe < xc ? -4 : 4), yb - 3, 'B', xe < xc ? 'end' : 'start') }

  // ---- section B-B: the deck of tray m seen from above, fixed size (not to the elevation's scale)
  const cx = 780, cy = 170, R = 80
  cap(650, 28, `SECTION B–B (TRAY ${m} DECK, SCHEMATIC)`)
  circ(cx, cy, R + 3, 'o2'); circ(cx, cy, R)
  const cd = 0.62 * R, hc = Math.sqrt(R * R - cd * cd) // chord at 0.62 R: downcomer segment (schematic)
  const out = m % 2 ? 1 : -1 // same side as the elevation shows for tray m
  line(cx + out * cd, cy - hc, cx + out * cd, cy + hc, 'o2') // outlet weir
  // tray 1 has no tray above: reflux enters there instead of a downcomer
  if (m > 1) line(cx - out * cd, cy - hc, cx - out * cd, cy + hc, 'hid') // downcomer from the tray above
  text(cx, cy + 4, 'Active area', 'middle')
  lead(cx + out * (R + 16), cy - R - 6, cx + out * (cd + 0.5 * (R - cd)), cy - 0.5 * hc, m === nT ? 'Downcomer to sump' : 'Downcomer', out > 0 ? 'start' : 'end')
  lead(cx - out * (R + 16), cy + R + 14, cx - out * (cd + 0.5 * (R - cd)), cy + 0.5 * hc, m === 1 ? 'Inlet (reflux)' : 'Inlet', out > 0 ? 'end' : 'start')
  lead(cx + out * (R + 16), cy + R + 14, cx + out * cd, cy + 0.6 * hc, 'Outlet weir', out > 0 ? 'start' : 'end')

  const notes = [
    'Heads, nozzles and tray layout schematic.',
    `${nT} real tray${nT === 1 ? '' : 's'}, spacing ${mm(H / nT)}; feed on tray ${f}.`,
    `Elevation approx. ${scaleText(sv)} at 1000 mm sheet width.`,
  ]
  if (ex > 1) notes.push(`Width drawn ×${ex < 10 ? ex.toFixed(1) : Math.round(ex)} so the trays stay visible.`)
  if (k > 1) notes.push(`1 tray in ${k} drawn, plus the feed, last and B–B trays.`)
  if (!downcomers) notes.push('Downcomers not drawn at this tray spacing.')
  notes.push('Dashed = hidden.')
  S.titleBlock('Distillation column — general arrangement (schematic)', notes, inputs)
  return S.finish(
    `Distillation column general arrangement, D ${mm(D)}, H ${mm(H)}, ${nT} trays`,
    `Schematic first-angle drawing of a tray column: front elevation with ${nT} trays, feed on tray ${f}, nozzles for vapour, reflux, feed, reboiler vapour and bottoms, a section B-B through one tray deck, and a title block listing the template inputs.`,
  )
}

// Process flow diagrams (PFD) for the ChemLab templates: a library of 12 simple unit symbols joined by streams.
// Schematic only: unit tags, stream names and a title. No process values appear, so every number on the
// page still comes from the template output. All text goes through `esc`; every other value is a number.
import { esc, n } from './sheet.ts'

type P = [number, number]
let diagrams = 0 // module counter keeps ids unique per call; no randomness needed

function canvas() {
  const id = `pfd${++diagrams}`
  const o: string[] = []
  const stream = (pts: P[]) => o.push(`<path class="s" d="M${pts.map(([x, y]) => `${n(x)} ${n(y)}`).join('L')}" marker-end="url(#${id}a)"/>`)
  const text = (x: number, y: number, t: string, anchor = 'middle', cls = '') =>
    o.push(`<text${cls ? ` class="${cls}"` : ''} x="${n(x)}" y="${n(y)}" text-anchor="${anchor}">${esc(t)}</text>`)
  const tag = (x: number, y: number, t: string, anchor = 'middle') => text(x, y, t, anchor, 'tag')
  const g = (body: string) => o.push(`<g class="u">${body}</g>`)
  const L = (x1: number, y1: number, x2: number, y2: number) => `<line x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}"/>`
  const R = (x: number, y: number, w: number, h: number, r = 0) => `<rect x="${n(x)}" y="${n(y)}" width="${n(w)}" height="${n(h)}" rx="${n(r)}"/>`
  const C = (x: number, y: number, r: number) => `<circle cx="${n(x)}" cy="${n(y)}" r="${n(r)}"/>`
  const D = (d: string, cls = '') => `<path${cls ? ` class="${cls}"` : ''} d="${d}"/>`
  const zig = (x1: number, x2: number, y: number, a = 6, k = 5) => {
    const dx = (x2 - x1) / (2 * k)
    let d = `M${n(x1)} ${n(y)}`
    for (let i = 0; i < 2 * k; i++) d += `L${n(x1 + (i + 1) * dx)} ${n(y + (i % 2 ? 0 : -a))}`
    return D(d)
  }
  return { id, o, stream, text, tag, g, L, R, C, D, zig }
}
type Cv = ReturnType<typeof canvas>

// ---- the 12 symbols: each is centred on (x, y) and written so the ports used by the flowsheets sit on its outline
export const SYMBOLS = ['cstr', 'pfr', 'batch', 'column', 'flash', 'hx', 'heater', 'condenser', 'reboiler', 'pump', 'valve', 'tee'] as const

const sym = {
  // stirred tank: body 64 x 84 (ports: left/right wall at y-24, top y-42, bottom y+42), shaft, impeller, motor
  cstr: (c: Cv, x: number, y: number) => c.g(c.R(x - 32, y - 42, 64, 84, 14) + c.L(x, y - 56, x, y + 22) + c.L(x - 14, y + 22, x + 14, y + 22) + c.R(x - 8, y - 66, 16, 10)
    + c.D(`M${x - 38} ${y + 4}V${y + 30}Q${x - 38} ${y + 42} ${x - 26} ${y + 42}`, 'j') + c.D(`M${x + 38} ${y + 4}V${y + 30}Q${x + 38} ${y + 42} ${x + 26} ${y + 42}`, 'j')),
  // tubular reactor: tube 140 x 32 (ports left/right at y) inside a dashed jacket (top/bottom at y-24)
  pfr: (c: Cv, x: number, y: number) => c.g(c.R(x - 70, y - 16, 140, 32, 16) + c.L(x - 40, y - 16, x - 40, y + 16) + c.L(x, y - 16, x, y + 16) + c.L(x + 40, y - 16, x + 40, y + 16)
    + c.R(x - 62, y - 24, 124, 48, 24).replace('<rect', '<rect class="j"')),
  // batch reactor: closed vessel (ports top/bottom) with agitator and a dashed jacket on the lower body (ports x-40 / x+40 at y+20)
  batch: (c: Cv, x: number, y: number) => c.g(c.R(x - 32, y - 42, 64, 84, 14) + c.L(x, y - 56, x, y + 22) + c.L(x - 14, y + 22, x + 14, y + 22) + c.R(x - 8, y - 66, 16, 10)
    + c.R(x - 40, y - 4, 80, 40, 8).replace('<rect', '<rect class="j"')),
  // distillation column: 52 x 160 (top/bottom ports at y -80/+80, side ports on the walls), tray lines
  column: (c: Cv, x: number, y: number) => c.g(c.R(x - 26, y - 80, 52, 160, 12) + [-50, -25, 0, 25, 50].map((d) => c.L(x - 20, y + d, x + 8, y + d) + c.L(x + 8, y + d, x + 8, y + d + 4)).join('')),
  // flash drum / vessel: 48 x 90 with a demister line (feed on the left wall at y, top and bottom ports)
  flash: (c: Cv, x: number, y: number) => c.g(c.R(x - 24, y - 45, 48, 90, 18) + c.D(`M${x - 24} ${y - 22}H${x + 24}`, 'j')),
  // shell-and-tube exchanger: circle r 22 with the tube line (ports left/right, top/bottom)
  hx: (c: Cv, x: number, y: number) => c.g(c.C(x, y, 22) + c.L(x - 22, y, x + 22, y)),
  // heater: box 60 x 40 with a heating coil (ports left/right at y)
  heater: (c: Cv, x: number, y: number) => c.g(c.R(x - 30, y - 20, 60, 40, 4) + c.zig(x - 24, x + 24, y + 4, 10, 4)),
  // condenser: horizontal shell 68 x 34 with a cooling coil (ports left/right at y, coolant at the bottom x-14 / x+14)
  condenser: (c: Cv, x: number, y: number) => c.g(c.R(x - 34, y - 17, 68, 34, 17) + c.zig(x - 22, x + 22, y + 5, 8, 5)),
  // reboiler (kettle): shell 68 x 36 with a weir at x+16 and a steam coil (left wall, top x-10, bottom x-12 / x+12)
  reboiler: (c: Cv, x: number, y: number) => c.g(c.R(x - 34, y - 18, 68, 36, 14) + c.L(x + 16, y - 18, x + 16, y + 6) + c.zig(x - 26, x + 8, y + 8, 8, 4)),
  // centrifugal pump: circle r 18 with a flow triangle (ports left/right at y)
  pump: (c: Cv, x: number, y: number) => c.g(c.C(x, y, 18) + c.D(`M${x - 8} ${y - 9}L${x + 10} ${y}L${x - 8} ${y + 9}Z`)),
  // valve: bowtie 28 x 20 with a stem (ports left/right at y)
  valve: (c: Cv, x: number, y: number) => c.g(c.D(`M${x - 14} ${y - 10}L${x + 14} ${y + 10}V${y - 10}L${x - 14} ${y + 10}Z`) + c.L(x, y, x, y - 18) + c.L(x - 7, y - 18, x + 7, y - 18)),
  // tee: mixer or splitter junction, a filled dot
  tee: (c: Cv, x: number, y: number) => c.o.push(`<circle class="dot" cx="${n(x)}" cy="${n(y)}" r="5"/>`),
}

type Draw = (c: Cv) => void
const wrap = (title: string, desc: string, draw: Draw): string => {
  const c = canvas()
  draw(c)
  const b = `#${c.id}b`
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 420" role="img" aria-labelledby="${c.id}t ${c.id}d">
<title id="${c.id}t">${esc(title)}</title><desc id="${c.id}d">${esc(desc)}</desc>
<defs><marker id="${c.id}a" viewBox="0 0 8 6" refX="8" refY="3" markerWidth="8" markerHeight="6" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 0L8 3L0 6Z" fill="#111"/></marker>
<style>${b} .u *{fill:#fff;stroke:#111;stroke-width:1.5}${b} .u .j{fill:none;stroke-dasharray:5 3;stroke-width:1}${b} .s{fill:none;stroke:#111;stroke-width:1.5}${b} .dot{fill:#111;stroke:#111}${b} text{font:11px Arial,sans-serif;fill:#111;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}${b} .tag{font-weight:700;font-size:12px}${b} .ttl{font-weight:700;font-size:15px}${b} .note{font-size:10px;fill:#444}</style></defs>
<g id="${c.id}b"><rect width="1000" height="420" fill="#fff"/><rect x="6" y="6" width="988" height="408" fill="none" stroke="#111" stroke-width="2"/>
<text class="ttl" x="24" y="34" text-anchor="start">${esc(title)}</text>
${c.o.join('\n')}
<text class="note" x="24" y="404" text-anchor="start">${esc('Schematic: unit tags and stream names only, no process values. Numbers are in the results above.')}</text>
</g></svg>
`
}

const S = sym
const flowsheets: Record<string, [string, string, Draw]> = {
  cstr: ['PFD: continuous stirred-tank reactor', 'Feed, pump P-101, heater E-101, jacketed reactor R-101 with coolant, product.', (c) => {
    c.stream([[40, 190], [152, 190]]); c.text(40, 180, 'Feed', 'start'); S.pump(c, 170, 190); c.tag(170, 226, 'P-101')
    c.stream([[188, 190], [300, 190]]); S.heater(c, 330, 190); c.tag(330, 226, 'E-101'); c.stream([[360, 190], [528, 190]])
    S.cstr(c, 560, 214); c.tag(620, 250, 'R-101', 'start'); c.text(620, 266, 'CSTR', 'start')
    c.stream([[592, 190], [940, 190]]); c.text(940, 180, 'Product', 'end')
    c.stream([[548, 365], [548, 262]]); c.text(540, 380, 'Coolant in', 'end'); c.stream([[572, 262], [572, 365]]); c.text(580, 380, 'Coolant out', 'start')
  }],
  batch: ['PFD: batch reactor', 'Charge through valve FV-101 into batch reactor R-101 with jacket, product to pump P-101.', (c) => {
    c.stream([[40, 100], [226, 100]]); c.text(40, 90, 'Charge', 'start'); S.valve(c, 240, 100); c.tag(240, 128, 'FV-101')
    c.stream([[254, 100], [436, 100], [436, 148]]); S.batch(c, 420, 190); c.tag(500, 160, 'R-101', 'start'); c.text(500, 176, 'Batch reactor', 'start')
    c.stream([[320, 210], [380, 210]]); c.text(320, 200, 'Utility in', 'start'); c.stream([[460, 210], [600, 210]]); c.text(606, 214, 'Utility out', 'start')
    c.stream([[420, 232], [420, 330], [582, 330]]); S.pump(c, 600, 330); c.tag(600, 366, 'P-101'); c.stream([[618, 330], [940, 330]]); c.text(940, 320, 'Product', 'end')
  }],
  pfr: ['PFD: plug-flow (tubular) reactor', 'Feed, pump P-101, heater E-101, tubular reactor R-101 with coolant jacket, product.', (c) => {
    c.stream([[40, 200], [152, 200]]); c.text(40, 190, 'Feed', 'start'); S.pump(c, 170, 200); c.tag(170, 236, 'P-101')
    c.stream([[188, 200], [300, 200]]); S.heater(c, 330, 200); c.tag(330, 236, 'E-101'); c.stream([[360, 200], [490, 200]])
    S.pfr(c, 560, 200); c.tag(560, 250, 'R-101'); c.text(560, 266, 'Tubular reactor')
    c.stream([[630, 200], [940, 200]]); c.text(940, 190, 'Product', 'end')
    c.stream([[520, 100], [520, 174]]); c.text(520, 92, 'Coolant in'); c.stream([[600, 174], [600, 100]]); c.text(600, 92, 'Coolant out')
  }],
  mccabe: ['PFD: distillation column', 'Feed heater E-101, column T-101, condenser E-102, reflux drum V-101, reflux pump P-101 and splitter, reboiler E-103.', (c) => {
    c.stream([[40, 205], [150, 205]]); c.text(40, 195, 'Feed', 'start'); S.heater(c, 180, 205); c.tag(180, 240, 'E-101'); c.stream([[210, 205], [304, 205]])
    S.column(c, 330, 205); c.tag(296, 134, 'T-101', 'end')
    c.stream([[356, 145], [466, 145]]); c.text(412, 136, 'Vapour'); S.condenser(c, 500, 145); c.tag(500, 118, 'E-102')
    c.stream([[486, 222], [486, 164]]); c.text(480, 232, 'Coolant in', 'end'); c.stream([[514, 164], [514, 222]]); c.text(520, 232, 'Coolant out', 'start')
    c.stream([[534, 145], [580, 145], [580, 170], [616, 170]]); S.flash(c, 640, 170); c.tag(672, 166, 'V-101', 'start'); c.text(672, 180, 'Reflux drum', 'start')
    c.stream([[640, 215], [640, 270], [682, 270]]); S.pump(c, 700, 270); c.tag(700, 306, 'P-101'); c.stream([[718, 270], [780, 270]]); S.tee(c, 780, 270)
    c.stream([[780, 270], [940, 270]]); c.text(940, 260, 'Distillate', 'end')
    c.stream([[780, 270], [780, 40], [330, 40], [330, 125]]); c.text(560, 32, 'Reflux')
    c.stream([[330, 285], [330, 320], [446, 320]]); S.reboiler(c, 480, 320); c.tag(526, 346, 'E-103', 'start')
    c.stream([[470, 302], [470, 265], [356, 265]]); c.text(412, 256, 'Boil-up')
    c.stream([[514, 320], [940, 320]]); c.text(940, 310, 'Bottoms', 'end')
    c.stream([[468, 380], [468, 338]]); c.text(460, 390, 'Steam', 'end'); c.stream([[492, 338], [492, 380]]); c.text(500, 390, 'Condensate', 'start')
  }],
  hx: ['PFD: shell-and-tube heat exchanger', 'Hot fluid through exchanger E-101 and valve FV-101; cold fluid pumped by P-101 through the exchanger.', (c) => {
    c.stream([[40, 200], [478, 200]]); c.text(40, 190, 'Hot fluid in', 'start'); S.hx(c, 500, 200); c.tag(536, 232, 'E-101', 'start')
    c.stream([[522, 200], [686, 200]]); S.valve(c, 700, 200); c.tag(700, 228, 'FV-101'); c.stream([[714, 200], [940, 200]]); c.text(940, 190, 'Hot fluid out', 'end')
    c.stream([[40, 330], [162, 330]]); c.text(40, 320, 'Cold fluid in', 'start'); S.pump(c, 180, 330); c.tag(180, 366, 'P-101')
    c.stream([[198, 330], [500, 330], [500, 222]]); c.stream([[500, 178], [500, 100], [940, 100]]); c.text(940, 90, 'Cold fluid out', 'end')
  }],
  flash: ['PFD: flash separation', 'Feed heater E-101 and valve FV-101 into flash drum V-101; vapour overhead, liquid through pump P-101.', (c) => {
    c.stream([[40, 200], [140, 200]]); c.text(40, 190, 'Feed', 'start'); S.heater(c, 170, 200); c.tag(170, 236, 'E-101'); c.stream([[200, 200], [306, 200]])
    S.valve(c, 320, 200); c.tag(320, 228, 'FV-101'); c.stream([[334, 200], [496, 200]])
    S.flash(c, 520, 200); c.tag(556, 160, 'V-101', 'start'); c.text(556, 176, 'Flash drum', 'start')
    c.stream([[520, 155], [520, 90], [940, 90]]); c.text(940, 80, 'Vapour', 'end')
    c.stream([[520, 245], [520, 330], [682, 330]]); S.pump(c, 700, 330); c.tag(700, 366, 'P-101'); c.stream([[718, 330], [940, 330]]); c.text(940, 320, 'Liquid', 'end')
  }],
  recycle: ['PFD: reactor, separator and recycle with purge', 'Fresh feed and recycle meet in mixer M-101, reactor R-101, separator V-101; overhead split at S-101 into purge and recycle.', (c) => {
    c.stream([[40, 200], [195, 200]]); c.text(40, 190, 'Fresh feed', 'start'); S.tee(c, 200, 200); c.tag(200, 226, 'M-101'); c.text(200, 240, 'Mixer')
    c.stream([[205, 200], [308, 200]]); S.pfr(c, 380, 200); c.tag(380, 250, 'R-101'); c.text(380, 266, 'Reactor')
    c.stream([[450, 200], [574, 200]]); S.flash(c, 600, 200); c.tag(636, 190, 'V-101', 'start'); c.text(636, 206, 'Separator', 'start')
    c.stream([[600, 155], [600, 115], [715, 115]]); c.text(600, 107, 'Vapour', 'end')
    S.tee(c, 720, 115); c.tag(734, 140, 'S-101', 'start'); c.text(734, 154, 'Splitter', 'start')
    c.stream([[720, 115], [720, 60], [200, 60], [200, 195]]); c.text(460, 52, 'Recycle')
    c.stream([[725, 115], [826, 115]]); S.valve(c, 840, 115); c.tag(840, 143, 'FV-101'); c.stream([[854, 115], [940, 115]]); c.text(940, 105, 'Purge', 'end')
    c.stream([[600, 245], [600, 330], [940, 330]]); c.text(940, 320, 'Product', 'end')
  }],
  pipe: ['PFD: pump and pipeline', 'Supply vessel TK-101, pump P-101, valve FV-101, pipeline with elevation rise to receiving vessel TK-102.', (c) => {
    S.flash(c, 100, 250); c.tag(134, 246, 'TK-101', 'start'); c.text(134, 260, 'Supply vessel', 'start')
    c.stream([[100, 295], [100, 325], [222, 325]]); c.text(106, 315, 'Suction', 'start'); S.pump(c, 240, 325); c.tag(240, 361, 'P-101')
    c.stream([[258, 325], [386, 325]]); c.text(300, 315, 'Discharge', 'start'); S.valve(c, 400, 325); c.tag(400, 353, 'FV-101')
    c.stream([[414, 325], [700, 325], [700, 140], [826, 140]]); c.text(520, 315, 'Pipeline and fittings', 'start'); c.text(692, 250, 'Elevation rise', 'end')
    S.flash(c, 850, 140); c.tag(850, 206, 'TK-102'); c.text(850, 220, 'Receiving vessel')
  }],
}

export function pfd(template: string): string | null {
  if (!Object.prototype.hasOwnProperty.call(flowsheets, template)) return null
  const [title, desc, draw] = flowsheets[template]
  return wrap(title, desc, draw)
}

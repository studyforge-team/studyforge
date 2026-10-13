// Shared SVG primitives for the ChemLab drawing sheets (column, heat exchanger): 1000 x 700 sheet,
// first-angle projection, title block. Every interpolated value is a number or escaped text.
export type Inputs = Record<string, { value: number; unit: string }>

let sheets = 0 // module counter keeps ids unique per call; no randomness needed
export const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
export const n = (v: number) => +v.toFixed(1)
export const mm = (m: number) => `${Math.round(m * 1000)} mm`
export const sig = (v: number) => String(+v.toPrecision(4))
// drawn 1 px = 1 mm on the sheet; k < 1 is an enlargement, written n:1 (never 1:0)
export const scaleText = (pxPerM: number) => {
  const k = 1000 / pxPerM
  return k >= 1 ? `1:${Math.round(k)}` : `${Math.round(1 / k)}:1`
}

export function sheet(prefix: string) {
  const id = `${prefix}${++sheets}`
  const A = `url(#${id}a)`
  const o: string[] = []
  const line = (x1: number, y1: number, x2: number, y2: number, cls = 'o') =>
    o.push(`<line class="${cls}" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}"/>`)
  const rect = (x: number, y: number, W: number, H: number, cls = 'o') =>
    o.push(`<rect class="${cls}" x="${n(x)}" y="${n(y)}" width="${n(W)}" height="${n(H)}"/>`)
  const circ = (x: number, y: number, R: number, cls = 'o') => o.push(`<circle class="${cls}" cx="${n(x)}" cy="${n(y)}" r="${n(R)}"/>`)
  const path = (d: string, cls = 'o') => o.push(`<path class="${cls}" d="${d}"/>`)
  const text = (x: number, y: number, t: string, anchor = 'start', rot = 0) =>
    o.push(`<text x="${n(x)}" y="${n(y)}" text-anchor="${anchor}"${rot ? ` transform="rotate(${rot} ${n(x)} ${n(y)})"` : ''}>${esc(t)}</text>`)
  const cap = (x: number, y: number, t: string) => o.push(`<text class="cap" x="${n(x)}" y="${n(y)}">${esc(t)}</text>`)
  // leader: label at the tail (x1,y1), arrowhead tip exactly on the part at (x2,y2)
  const lead = (x1: number, y1: number, x2: number, y2: number, t: string, anchor = 'start') => {
    o.push(`<line class="l" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}" marker-end="${A}"/>`)
    text(x1 + (anchor === 'start' ? 4 : anchor === 'end' ? -4 : 0), y1 + 3, t, anchor)
  }
  const arrow = (x1: number, y1: number, x2: number, y2: number) =>
    o.push(`<line class="l" x1="${n(x1)}" y1="${n(y1)}" x2="${n(x2)}" y2="${n(y2)}" marker-end="${A}"/>`)
  const dimV = (x: number, y1: number, y2: number, xFrom: number, t: string) => {
    line(xFrom, y1, x - 4, y1, 'e'); line(xFrom, y2, x - 4, y2, 'e')
    o.push(`<line class="l" x1="${n(x)}" y1="${n(y1)}" x2="${n(x)}" y2="${n(y2)}" marker-start="${A}" marker-end="${A}"/>`)
    text(x - 4, (y1 + y2) / 2, t, 'middle', -90)
  }
  // text centred above the line, or (left = true) to the left of it, clear of anything below the part
  const dimH = (y: number, x1: number, x2: number, yFrom: number, t: string, left = false) => {
    line(x1, yFrom, x1, y + 4, 'e'); line(x2, yFrom, x2, y + 4, 'e')
    o.push(`<line class="l" x1="${n(x1)}" y1="${n(y)}" x2="${n(x2)}" y2="${n(y)}" marker-start="${A}" marker-end="${A}"/>`)
    if (left) text(x1 - 8, y + 4, t, 'end')
    else text((x1 + x2) / 2, y - 4, t, 'middle')
  }
  // first-angle symbol (IS SP 46) above the title block; the block lists notes then the template inputs
  const titleBlock = (heading: string, notes: string[], inputs: Inputs) => {
    const rows = Object.entries(inputs)
    const bh = 32 + notes.length * 14 + 16 + rows.length * 14 + 8
    const bx = 640, by = 685 - bh
    const sx = 672, sy = by - 40
    o.push(`<g class="sym"><path d="M${sx} ${sy - 10}H${sx + 34}L${sx + 40} ${sy - 18}V${sy + 18}L${sx + 34} ${sy + 10}H${sx}Z"/>`)
    o.push(`<line class="e" x1="${sx - 6}" y1="${sy}" x2="${sx + 52}" y2="${sy}"/>`)
    o.push(`<circle cx="${sx + 82}" cy="${sy}" r="18"/><circle cx="${sx + 82}" cy="${sy}" r="10"/></g>`)
    text(sx + 108, sy + 4, 'FIRST ANGLE PROJECTION')
    rect(bx, by, 340, bh, 'tb')
    line(bx, by + 26, bx + 340, by + 26, 'e')
    text(bx + 8, by + 17, heading)
    notes.forEach((t, i) => text(bx + 8, by + 42 + i * 14, t))
    const yi = by + 42 + notes.length * 14
    text(bx + 8, yi, 'Template inputs:')
    rows.forEach(([k, v], i) => text(bx + 8, yi + 16 + i * 14, `${k} = ${sig(v.value)} ${v.unit}`))
    return by - 60 // top of the symbol area: views must stay above this on the right
  }
  const finish = (title: string, desc: string, defs = '') => {
    const b = `#${id}b`
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 700" role="img" aria-labelledby="${id}t ${id}d">
<title id="${id}t">${esc(title)}</title><desc id="${id}d">${esc(desc)}</desc>
<defs><marker id="${id}a" viewBox="0 0 8 6" refX="8" refY="3" markerWidth="8" markerHeight="6" markerUnits="userSpaceOnUse" orient="auto-start-reverse"><path d="M0 0L8 3L0 6Z" fill="#111"/></marker>
<pattern id="${id}h" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="#111" stroke-width="1"/></pattern>${defs}
<style>${b} .o,${b} .o2,${b} .noz,${b} .tb,${b} .sym *,${b} .sym{fill:none;stroke:#111;stroke-width:1}${b} .o2{stroke-width:2}${b} .noz{fill:#fff;stroke-width:1.5}${b} .tray{stroke:#111;stroke-width:1.4}${b} .feed{stroke:#b91c1c;stroke-width:2}${b} .liq{fill:#dbeafe;stroke:none}${b} .hid{fill:none;stroke:#111;stroke-dasharray:5 3}${b} .l,${b} .e{stroke:#111;stroke-width:.7;fill:none}${b} .cl{stroke:#111;stroke-width:.7;stroke-dasharray:14 3 2 3;fill:none}${b} .cut{fill:url(#${id}h);stroke:#111;stroke-width:.6}${b} .tube{fill:#fff;stroke:#111;stroke-width:.7}${b} text{font:11px Arial,sans-serif;fill:#111;paint-order:stroke;stroke:#fff;stroke-width:3px;stroke-linejoin:round}${b} .cap{font-weight:700;font-size:12px}</style></defs>
<g id="${id}b"><rect width="1000" height="700" fill="#fff"/><rect class="o2" x="10" y="10" width="980" height="680" fill="none"/>
${o.join('\n')}
</g></svg>
`
  }
  return { id, o, line, rect, circ, path, text, cap, lead, arrow, dimV, dimH, titleBlock, finish }
}

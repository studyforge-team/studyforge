import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { fmt } from '@/lib/fmt'
import { Button } from '@/components/ui/button'

// Imperative three.js, render on demand (no animation loop). `T0`..`Tmax` map blue -> red.
export type Cstr3DProps = { D: number; H: number; T: number; T0: number; Tmax: number; UA: number }
const LABELS = ['Jacket', 'Agitator (D/3)', 'Feed in', 'Product out']
const hue = (p: Cstr3DProps) => 0.61 * (1 - Math.min(1, Math.max(0, p.Tmax > p.T0 ? (p.T - p.T0) / (p.Tmax - p.T0) : 0)))
const css = (p: Cstr3DProps) => `hsl(${Math.round(hue(p) * 360)} 80% 50%)`

type Api = { shape: (D: number, H: number, UA: number) => void; paint: (p: Cstr3DProps) => void; png: () => string }

export default function Cstr3D(p: Cstr3DProps) {
  const [fb, setFb] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const cv = useRef<HTMLCanvasElement>(null)
  const lab = useRef<(HTMLSpanElement | null)[]>([])
  const api = useRef<Api>(null)

  useEffect(() => {
    if (fb || !cv.current || !box.current) return
    const canvas = cv.current, el = box.current
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true }) } catch { queueMicrotask(() => setFb(true)); return } // no WebGL -> 2D drawing
    renderer.setClearColor(0xe9ecef)
    renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5))
    const scene = new THREE.Scene()
    scene.add(new THREE.AmbientLight(0xffffff, 1.2))
    const sun = new THREE.DirectionalLight(0xffffff, 2.2)
    sun.position.set(3, 5, 4)
    scene.add(sun)
    const cam = new THREE.PerspectiveCamera(35, 1, 0.01, 100)
    const ctl = new OrbitControls(cam, canvas)
    let group: THREE.Group | undefined
    let anchors: (THREE.Vector3 | null)[] = []
    let first = true
    let liquidMat: THREE.MeshStandardMaterial | undefined
    let last = ''

    const render = () => {
      renderer.render(scene, cam)
      const w = el.clientWidth, h = el.clientHeight
      anchors.forEach((a, i) => {
        const s = lab.current[i]
        if (!s) return
        const v = a?.clone().project(cam)
        s.style.display = v && v.z < 1 ? '' : 'none'
        if (!v) return
        const x = Math.min(w - s.offsetWidth, Math.max(0, ((v.x + 1) / 2) * w - s.offsetWidth / 2))
        const y = Math.min(h - s.offsetHeight, Math.max(0, ((1 - v.y) / 2) * h - s.offsetHeight / 2))
        s.style.transform = `translate(${x}px,${y}px)`
      })
      canvas.dataset.dist = cam.position.distanceTo(ctl.target).toFixed(4) // zoom-kept check hook
      canvas.dataset.geoms = String(renderer.info.memory.geometries) // leak check hook for the verify script
    }
    const fit = () => { // keep the whole vessel in view for any aspect ratio
      if (!group) return
      const sph = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere())
      const vf = (35 * Math.PI) / 180, hf = 2 * Math.atan(Math.tan(vf / 2) * cam.aspect)
      const dist = (sph.radius / Math.sin(Math.min(vf, hf) / 2)) * 1.08
      const dir = first ? new THREE.Vector3(0.2, 0.35, 0.9) : cam.position.clone().sub(ctl.target)
      first = false
      ctl.target.copy(sph.center)
      cam.position.copy(sph.center).add(dir.normalize().multiplyScalar(dist))
      ctl.minDistance = dist / 3; ctl.maxDistance = dist * 3
      ctl.update()
    }
    const size = () => {
      renderer.setSize(el.clientWidth, el.clientHeight, false)
      cam.aspect = el.clientWidth / el.clientHeight
      cam.updateProjectionMatrix()
      fit(); render()
    }
    const free = () => group?.traverse((o) => { const m = o as THREE.Mesh; if (m.isMesh) { m.geometry.dispose(); (m.material as THREE.Material).dispose() } })

    api.current = {
      png: () => { render(); return canvas.toDataURL('image/png') }, // same tick: no preserveDrawingBuffer
      paint: (q) => { liquidMat?.color.setHSL(hue(q), 0.8, 0.5); render() }, // colour only: no geometry work, no fit
      shape: (D, H, UA) => {
        const key = `${D}|${H}|${UA > 0}`
        if (key === last) return
        const refit = !group || last.split('|').slice(0, 2).join('|') !== `${D}|${H}`
        last = key
        const q = { D, H, UA }
        if (group) { scene.remove(group); free() }
        group = new THREE.Group()
        const k = 2 / Math.max(q.D, q.H), r = (q.D * k) / 2, h = q.H * k, yb = -h / 2
        const add = (g: THREE.BufferGeometry, color: THREE.ColorRepresentation, op = 1, x = 0, y = 0, rz = 0) => {
          const m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color, transparent: op < 1, opacity: op, depthWrite: op === 1, side: op < 1 ? THREE.DoubleSide : THREE.FrontSide }))
          m.position.set(x, y, 0); m.rotation.z = rz; group!.add(m)
        }
        add(new THREE.CylinderGeometry(r * 0.98, r * 0.98, h * 0.98, 48), 0x888888, 0.55)
        liquidMat = (group.children[0] as THREE.Mesh).material as THREE.MeshStandardMaterial
        add(new THREE.CylinderGeometry(r, r, h, 48, 1, true), 0xcccccc, 0.25)
        if (q.UA > 0) add(new THREE.CylinderGeometry(r * 1.12, r * 1.12, h * 0.8, 48, 1, true), 0x3b82f6, 0.2, 0, yb + h * 0.4) // ponytail: no jacket when adiabatic
        const yi = yb + h / 3, id = (2 * r) / 3
        add(new THREE.CylinderGeometry(0.02, 0.02, h / 2 + 0.2 - yi, 8), 0x555555, 1, 0, (h / 2 + 0.2 + yi) / 2)
        add(new THREE.BoxGeometry(id, 0.05, 0.04), 0x333333, 1, 0, yi)
        const blade = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.05, id), new THREE.MeshStandardMaterial({ color: 0x333333 })); blade.position.y = yi; group.add(blade)
        const nz = r * 0.6, np = (x: number, y: number) => add(new THREE.CylinderGeometry(r * 0.07, r * 0.07, nz, 12), 0x888888, 1, x, y, Math.PI / 2)
        const yIn = h / 2 - h * 0.12, yOut = yb + h * 0.12
        np(-r - nz / 2 + r * 0.05, yIn); np(r + nz / 2 - r * 0.05, yOut)
        group.position.set(0, 0, 0)
        scene.add(group)
        anchors = [q.UA > 0 ? new THREE.Vector3(r * 1.12, yb + h * 0.27, 0) : null, new THREE.Vector3(r * 0.2, yi + h * 0.12, 0), new THREE.Vector3(-r - nz, yIn, 0), new THREE.Vector3(r + nz, yOut, 0)]
        if (refit) fit()
        render()
      },
    }

    ctl.addEventListener('change', render)
    // FPS probe: while the user orbits, count frames for 2 s; < 20 fps -> 2D drawing. Once per mount.
    let probed = false, drag = false
    ctl.addEventListener('start', () => {
      drag = true
      if (probed) return
      probed = true
      const t0 = performance.now()
      let n = 0
      const tick = () => {
        if (!drag || document.hidden) return // short or backgrounded orbit proves nothing
        n++; render()
        if (performance.now() - t0 < 2000) requestAnimationFrame(tick)
        else if (n / 2 < 20) setFb(true)
      }
      requestAnimationFrame(tick)
    })
    ctl.addEventListener('end', () => { drag = false })
    const lost = (e: Event) => { e.preventDefault(); setFb(true) }
    canvas.addEventListener('webglcontextlost', lost)
    const ro = new ResizeObserver(size)
    ro.observe(el)

    return () => {
      api.current = null
      ro.disconnect()
      canvas.removeEventListener('webglcontextlost', lost)
      ctl.dispose(); free(); renderer.dispose()
    }
  }, [fb])

  // One rAF per change (cancelled by the next) so the result numbers paint before any 3D work.
  useEffect(() => {
    const id = requestAnimationFrame(() => { api.current?.shape(p.D, p.H, p.UA); api.current?.paint(p) })
    return () => cancelAnimationFrame(id)
  }, [p.D, p.H, p.UA > 0, p.T, p.T0, p.Tmax, fb]) // eslint-disable-line

  const desc = `Stirred-tank reactor, diameter ${fmt(p.D)} m, height ${fmt(p.H)} m, liquid at ${fmt(p.T)} K`
  const png = () => {
    const url = api.current?.png()
    if (!url) return
    const a = document.createElement('a')
    a.href = url; a.download = 'cstr.png'; a.click()
  }
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-base font-semibold">3D view</h2>
      <p data-t3d className="mt-1 flex items-center gap-2 text-sm">
        <span aria-hidden="true" className="inline-block h-3 w-16 rounded" style={{ background: 'linear-gradient(to right, hsl(220 80% 50%), hsl(0 80% 50%))' }} />
        <span className="text-xs text-muted-foreground">{fmt(p.T0)} K to {fmt(p.Tmax)} K</span>
        <b className="tabular-nums" style={{ color: css(p) }}>T = {fmt(p.T)} K</b>
      </p>
      {fb ? <Flat {...p} desc={desc} /> : (
        <>
          <div ref={box} className="relative mt-2 aspect-square w-full overflow-hidden rounded-lg border bg-background sm:aspect-[4/3]">
            <canvas ref={cv} role="img" aria-label={desc} className="size-full" />
            {LABELS.map((t, i) => <span key={t} ref={(e) => { lab.current[i] = e }} className="pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded bg-background/80 px-1 text-xs">{t}</span>)}
            <span className="pointer-events-none absolute bottom-1 left-1 rounded bg-background/80 px-1 text-xs tabular-nums">D = {fmt(p.D)} m, H = {fmt(p.H)} m</span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Drag to rotate, pinch or scroll to zoom</p>
          <Button className="mt-2 h-11" variant="outline" onClick={png}>Download PNG</Button>
        </>
      )}
    </section>
  )
}

// Placeholder 2D front view. ponytail: P2's V2Da cstrViews() (PR #13, not merged) replaces this later.
function Flat({ D, H, UA, desc, ...p }: Cstr3DProps & { desc: string }) {
  const k = 150 / Math.max(D, H), w = D * k, h = H * k, x = 100, y = 20, yi = y + h * (2 / 3)
  return (
    <>
      <svg viewBox="0 0 360 240" role="img" aria-label={desc} className="mt-2 w-full max-w-md text-foreground" fontSize="11" fill="currentColor" stroke="currentColor">
        <rect x={x} y={y} width={w} height={h} strokeWidth="2" style={{ fill: css({ D, H, UA, ...p }), fillOpacity: 0.5 }} />
        {UA > 0 && <rect x={x - 6} y={y + h * 0.2} width={w + 12} height={h * 0.8} fill="none" stroke="#3b82f6" strokeWidth="2" strokeDasharray="4 3" />}
        <path d={`M${x + w / 2} ${y - 10}V${yi}M${x + w / 2 - w / 6} ${yi}H${x + w / 2 + w / 6}`} strokeWidth="3" fill="none" />
        <path d={`M${x - 25} ${y + h * 0.12}H${x}M${x + w} ${y + h * 0.88}H${x + w + 25}`} strokeWidth="4" fill="none" />
        <text x={x - 28} y={y + h * 0.12 - 6} textAnchor="end" stroke="none">Feed in</text>
        <text x={x + w + 4} y={y + h * 0.88 + 16} stroke="none">Product out</text>
        {UA > 0 && <text x={x - 10} y={y + h * 0.5} textAnchor="end" stroke="none">Jacket</text>}
        <text x={x + w / 2 - 6} y={yi - 22} textAnchor="end" stroke="none">Agitator<tspan x={x + w / 2 - 6} dy="12">(D/3)</tspan></text>
        <path d={`M${x} ${y + h + 12}H${x + w}M${x + w + 70} ${y}V${y + h}`} fill="none" strokeWidth="1" />
        <text x={x + w / 2} y={y + h + 26} textAnchor="middle" stroke="none">D = {fmt(D)} m</text>
        <text transform={`translate(${x + w + 84} ${y + h / 2}) rotate(-90)`} textAnchor="middle" stroke="none">H = {fmt(H)} m</text>
      </svg>
      <p className="mt-1 text-sm text-muted-foreground">3D isn't available on this device — showing the 2D drawing.</p>
    </>
  )
}

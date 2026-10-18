import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { fmt } from '@/lib/fmt'
import { Button } from '@/components/ui/button'
import { tubeLayout, type HxGeometry } from '@/chemlab/drawings/hx'
import type { ColumnGeometry } from '@/chemlab/drawings/column'

// Imperative three.js, render on demand (no animation loop); same scaffolding as Cstr3D (V3Da).
// Trays / tubes are InstancedMesh; over the triangle budget a subset is drawn and the real count is written.
export type Equip3DProps = { kind: 'column'; g: ColumnGeometry } | { kind: 'hx'; g: HxGeometry }
const MAX_TRIS = 30000
const tubeBudget = (other: number, perItem: number) => Math.max(1, Math.floor((MAX_TRIS - other) / perItem))

type Api = { shape: (p: Equip3DProps) => void; png: () => string }
const tris = (g: THREE.BufferGeometry) => (g.index ? g.index.count : g.attributes.position.count) / 3
const keyOf = (p: Equip3DProps) => (p.kind === 'column' ? [p.g.diameter_m, p.g.height_m, Math.round(p.g.n_trays), p.g.feed_tray] : [p.g.shell_diameter_m, p.g.tube_length_m, p.g.n_tubes, p.g.tube_od_m, p.g.pitch_m]).join('|')
const sizeOf = (p: Equip3DProps) => (p.kind === 'column' ? [p.g.diameter_m, p.g.height_m] : [p.g.shell_diameter_m, p.g.tube_length_m]).join('|')
const exOf = (p: Equip3DProps) => Math.max(1, p.kind === 'column' ? p.g.height_m / (12 * p.g.diameter_m) : p.g.tube_length_m / (4 * p.g.shell_diameter_m)) // radial exaggeration, as the 2D sheet
const exTxt = (p: Equip3DProps) => { const e = exOf(p); return e > 1 ? ` · diameter drawn ×${e.toFixed(1)} for clarity` : '' }
const labelsOf = (kind: string) => kind === 'column' ? ['Feed', 'Vapour to condenser', 'Bottoms to reboiler'] : ['Tube side in', 'Tube side out', 'Shell side in', 'Shell side out']

export default function Equip3D(p: Equip3DProps) {
  const [fb, setFb] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  const cv = useRef<HTMLCanvasElement>(null)
  const lab = useRef<(HTMLSpanElement | null)[]>([])
  const note = useRef<HTMLSpanElement>(null)
  const api = useRef<Api>(null)
  const col = p.kind === 'column'

  useEffect(() => {
    if (fb || !cv.current || !box.current) return
    const canvas = cv.current, el = box.current
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true }) } catch { queueMicrotask(() => setFb(true)); return }
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
    let anchors: THREE.Vector3[] = []
    let first = true, last = '', lastSize = ''

    const render = () => {
      renderer.render(scene, cam)
      const w = el.clientWidth, h = el.clientHeight
      anchors.forEach((a, i) => {
        const s = lab.current[i]
        if (!s) return
        const v = a.clone().project(cam)
        s.style.display = v.z < 1 ? '' : 'none'
        const x = Math.min(w - s.offsetWidth, Math.max(0, ((v.x + 1) / 2) * w - s.offsetWidth / 2))
        const y = Math.min(h - s.offsetHeight, Math.max(0, ((1 - v.y) / 2) * h - s.offsetHeight / 2))
        s.style.transform = `translate(${x}px,${y}px)`
      })
      canvas.dataset.tris = String(renderer.info.render.triangles) // test hook: budget check
    }
    const fit = () => {
      if (!group) return
      const sph = new THREE.Box3().setFromObject(group).getBoundingSphere(new THREE.Sphere())
      const vf = (35 * Math.PI) / 180, hf = 2 * Math.atan(Math.tan(vf / 2) * cam.aspect)
      const dist = (sph.radius / Math.sin(Math.min(vf, hf) / 2)) * 1.08
      const dir = first ? new THREE.Vector3(0.5, 0.35, 0.9) : cam.position.clone().sub(ctl.target)
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
      shape: (q) => {
        const key = keyOf(q)
        if (key === last) return
        last = key
        const refit = !group || lastSize !== sizeOf(q)
        lastSize = sizeOf(q)
        if (group) { scene.remove(group); free() }
        group = new THREE.Group()
        let fixed = 0 // triangles of everything except the instanced items
        const add = (g: THREE.BufferGeometry, color: THREE.ColorRepresentation, op = 1) => {
          fixed += tris(g) * (op < 1 ? 2 : 1) // transparent double-sided materials render two passes
          group!.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color, transparent: op < 1, opacity: op, depthWrite: op === 1, side: op < 1 ? THREE.DoubleSide : THREE.FrontSide })))
        }
        const inst = (g: THREE.BufferGeometry, ms: THREE.Matrix4[], colors?: THREE.Color[], base = 0xffffff) => {
          const m = new THREE.InstancedMesh(g, new THREE.MeshStandardMaterial({ color: base }), ms.length)
          ms.forEach((x, i) => { m.setMatrixAt(i, x); if (colors) m.setColorAt(i, colors[i]) })
          group!.add(m)
        }
        const at = (x: number, y: number, z: number) => new THREE.Matrix4().setPosition(x, y, z)
        let msg = '', count = 0
        if (q.kind === 'column') {
          const { diameter_m: D, height_m: H } = q.g, n = Math.max(1, Math.round(q.g.n_trays)), f = Math.min(n, Math.max(1, Math.round(q.g.feed_tray)))
          const ex = exOf(q), k = 2 / (H + D / 2), r = (D * k * ex) / 2, h = H * k, sp = h / n, yT = (i: number) => h / 2 - (i - 0.5) * sp
          add(new THREE.CylinderGeometry(r, r, h, 48, 1, true), 0xcccccc, 0.3)
          const head = new THREE.SphereGeometry(r, 32, 8, 0, 2 * Math.PI, 0, Math.PI / 2).scale(1, 0.5, 1) // 2:1 elliptical (head height = drawn r/2)
          add(head.clone().translate(0, h / 2, 0), 0xcccccc, 0.3)
          add(head.clone().rotateX(Math.PI).translate(0, -h / 2, 0), 0xcccccc, 0.3)
          const nz = r * 0.6, nr = r * 0.07, ny = (y: number) => new THREE.CylinderGeometry(nr, nr, nz, 12).translate(0, y, 0)
          add(new THREE.CylinderGeometry(nr, nr, nz, 12).rotateZ(Math.PI / 2).translate(-r - nz / 2 + nr, yT(f) - 0.3 * sp, 0), 0x888888)
          add(ny(h / 2 + r / 2 + nz / 2 - r * 0.1), 0x888888)
          add(ny(-h / 2 - r / 2 - nz / 2 + r * 0.1), 0x888888)
          const tray = new THREE.CylinderGeometry(r * 0.98, r * 0.98, Math.min(0.12 * sp, 0.03), 16), dc = new THREE.BoxGeometry(0.06 * r, 0.75 * sp, 1.2 * r)
          const step = Math.ceil(n / Math.max(1, tubeBudget(fixed, tris(tray) + tris(dc)) - 1)) // ponytail: every step-th tray when over budget
          const idx: number[] = []
          for (let i = 1; i <= n; i++) if ((i - 1) % step === 0 || i === f) idx.push(i)
          count = idx.length
          inst(tray, idx.map((i) => at(0, yT(i), 0)), idx.map((i) => new THREE.Color(i === f ? 0xdc2626 : 0x8a8f98)))
          inst(dc, idx.map((i) => at((i % 2 ? 0.6 : -0.6) * r, yT(i) - 0.375 * sp, 0)))
          if (count < n) msg = `Showing ${count} of ${n} trays`
          anchors = [new THREE.Vector3(-r - nz, yT(f), 0), new THREE.Vector3(0, h / 2 + r / 2 + nz, 0), new THREE.Vector3(0, -h / 2 - r / 2 - nz, 0)]
        } else {
          const g = q.g, Ds = g.shell_diameter_m, L = g.tube_length_m, ex = exOf(q), k = 2 / (L + 0.75 * Ds * ex), r = (Ds * k * ex) / 2, l = L * k
          const ch = r // channel 0.5 Ds long
          const rot = (c: THREE.CylinderGeometry) => c.rotateZ(Math.PI / 2)
          add(rot(new THREE.CylinderGeometry(r, r, l, 48, 1, true)).translate(l / 2, 0, 0), 0xcccccc, 0.3)
          add(rot(new THREE.CylinderGeometry(r, r, ch, 48)).translate(-ch / 2, 0, 0), 0xcccccc, 0.3)
          add(new THREE.SphereGeometry(r, 32, 8, 0, 2 * Math.PI, 0, Math.PI / 2).scale(1, 0.5, 1).rotateZ(-Math.PI / 2).translate(l, 0, 0), 0xcccccc, 0.3)
          for (const x of [0, l]) add(rot(new THREE.CylinderGeometry(r, r, 0.02, 48)).translate(x, 0, 0), 0x555555)
          const nr = r * 0.12, nl = r * 0.5, noz = (x: number, s: number) => new THREE.CylinderGeometry(nr, nr, nl, 12).translate(x, s * (r + nl / 2 - nr), 0)
          add(noz(-ch / 2, -1), 0x888888); add(noz(-ch / 2, 1), 0x888888) // tube side: in below, out above
          add(noz(l * 0.2, 1), 0x888888); add(noz(l * 0.8, -1), 0x888888) // shell side
          const tube = rot(new THREE.CylinderGeometry(1, 1, 1, 8, 1, true)) // unit tube, scaled per instance
          const max = tubeBudget(fixed, tris(tube))
          const pts = tubeLayout(Math.min(Math.round(g.n_tubes), max), g.pitch_m) // innermost max tubes, both passes
          count = pts.length
          const rt = (g.tube_od_m * k * ex) / 2
          inst(tube, pts.map(([x, y]) => new THREE.Matrix4().compose(new THREE.Vector3(l / 2, y * k * ex, x * k * ex), new THREE.Quaternion(), new THREE.Vector3(l, rt, rt))), undefined, 0xb87333) // copper
          if (count < g.n_tubes) msg = `Showing ${count} of ${Math.round(g.n_tubes)} tubes`
          const ya = r + nl
          anchors = [new THREE.Vector3(-ch / 2, -ya, 0), new THREE.Vector3(-ch / 2, ya, 0), new THREE.Vector3(l * 0.2, ya, 0), new THREE.Vector3(l * 0.8, -ya, 0)]
        }
        if (note.current) note.current.textContent = msg
        canvas.dataset.instances = String(count)
        scene.add(group)
        if (refit) fit()
        render()
      },
    }

    ctl.addEventListener('change', render)
    let probed = false, drag = false // FPS probe: first orbit counts frames for 2 s; < 20 fps -> 2D drawing
    ctl.addEventListener('start', () => {
      drag = true
      if (probed) return
      probed = true
      const t0 = performance.now()
      let n = 0
      const tick = () => {
        if (!drag || document.hidden) return
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

  const key = keyOf(p)
  useEffect(() => {
    const id = requestAnimationFrame(() => api.current?.shape(p))
    return () => cancelAnimationFrame(id)
  }, [key, fb]) // eslint-disable-line

  const desc = p.kind === 'column'
    ? `Distillation column, diameter ${fmt(p.g.diameter_m)} m, height ${fmt(p.g.height_m)} m, ${Math.round(p.g.n_trays)} real trays, feed on tray ${Math.round(p.g.feed_tray)}${exTxt(p) && ', diameter exaggerated for clarity'}`
    : `Shell-and-tube heat exchanger, shell diameter ${fmt(p.g.shell_diameter_m)} m, tube length ${fmt(p.g.tube_length_m)} m, ${Math.round(p.g.n_tubes)} tubes, tube OD ${fmt(p.g.tube_od_m * 1000)} mm${exTxt(p) && ', diameter exaggerated for clarity'}`
  const cap = p.kind === 'column'
    ? `D = ${fmt(p.g.diameter_m)} m, H = ${fmt(p.g.height_m)} m, ${Math.round(p.g.n_trays)} real trays`
    : `Shell D = ${fmt(p.g.shell_diameter_m)} m, L = ${fmt(p.g.tube_length_m)} m, ${Math.round(p.g.n_tubes)} tubes, OD ${fmt(p.g.tube_od_m * 1000)} mm`
  const png = () => {
    const url = api.current?.png()
    if (!url) return
    const a = document.createElement('a')
    a.href = url; a.download = col ? 'column.png' : 'exchanger.png'; a.click()
  }
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-base font-semibold">3D view</h2>
      {fb ? <p className="mt-2 text-sm text-muted-foreground">3D isn't available on this device — see the 2D drawing below.</p> : (
        <>
          <div ref={box} className="relative mt-2 aspect-square w-full overflow-hidden rounded-lg border bg-background sm:aspect-[4/3]">
            <canvas ref={cv} role="img" aria-label={desc} className="size-full" />
            {labelsOf(p.kind).map((t, i) => <span key={t} ref={(e) => { lab.current[i] = e }} className="pointer-events-none absolute left-0 top-0 whitespace-nowrap rounded bg-background/80 px-1 text-xs">{p.kind === 'column' && i === 0 ? `Feed (tray ${Math.round(p.g.feed_tray)})` : t}</span>)}
            <span className="pointer-events-none absolute bottom-1 left-1 rounded bg-background/80 px-1 text-xs tabular-nums">{cap}{exTxt(p)}</span>
            <span ref={note} data-subset className="pointer-events-none absolute right-1 top-1 rounded bg-background/80 px-1 text-xs" />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Drag to rotate, pinch or scroll to zoom. Diameter and heads are illustrative.</p>
          <Button className="mt-2 h-11" variant="outline" onClick={png}>Download PNG</Button>
        </>
      )}
    </section>
  )
}

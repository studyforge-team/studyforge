// Main-thread side of the sandbox. One worker, one job at a time, 10 s kill timer, respawn on failure.
// Every message from the worker is untrusted (Python can call js.postMessage): it is shape-checked and
// dropped unless it is the type/id we are waiting for. Callers must render `stdout` as TEXT, never innerHTML.
export type SandboxResult =
  | { ok: true; result: unknown; stdout: string; figures: string[]; ms: number }
  | { ok: false; error: string }
type Mode = 'solve' | 'chemlab'
type Msg = { type: string; id?: number; error?: string; needsRespawn?: string[]; result?: unknown; stdout?: string; figures?: string[]; ms?: number }

const KILL_MS = 10_000
const PNG = 'iVBORw0KGgo'

let worker: Worker | undefined
let ready: Promise<string | undefined> | undefined // resolves to an error string, or undefined when up
let packages: string[] = [] // extra packages to load at init (grows via needsRespawn)
let waiter: ((m: Msg) => void) | undefined
let expect: { types: string[]; id?: number } = { types: [] }
let seq = 0
// ponytail: one-at-a-time promise chain; no cancellation of the running job except by the 10 s kill.
let tail: Promise<unknown> = Promise.resolve()
const pending = new Set<{ latest: boolean; resolve: (r: SandboxResult) => void }>()

const isStr = (x: unknown) => typeof x === 'string'
function shapeOk(d: Msg): boolean {
  switch (d.type) {
    case 'ready': return typeof d.ms === 'number'
    case 'started': return true
    case 'fatal': return isStr(d.error)
    case 'error': return isStr(d.error) && (d.needsRespawn === undefined || (Array.isArray(d.needsRespawn) && d.needsRespawn.every(isStr)))
    case 'result': return isStr(d.stdout) && typeof d.ms === 'number' && Array.isArray(d.figures) && d.figures.every((f) => isStr(f) && f.startsWith(PNG))
    default: return false
  }
}

function discard() {
  worker?.terminate()
  worker = ready = waiter = undefined
}

// Sends msg and resolves with the first valid reply of an expected type (plus 'fatal', which has no id).
function request(msg: unknown, types: string[], id: number | undefined, onStarted?: () => void) {
  return new Promise<Msg>((resolve) => {
    expect = { types: [...types, 'fatal'], id }
    waiter = (m) => {
      if (m.type === 'started') return onStarted?.()
      waiter = undefined
      resolve(m)
    }
    worker!.postMessage(msg)
  })
}

function boot(): Promise<string | undefined> {
  if (worker) return ready!
  const w = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
  worker = w
  w.onmessage = ({ data }: MessageEvent<unknown>) => {
    const d = data as Msg | null
    const ok = waiter && d && typeof d === 'object' && expect.types.includes(d.type) &&
      (d.type === 'fatal' || d.id === expect.id) && shapeOk(d)
    if (ok) waiter!(d!)
    else console.warn('sandbox: dropped message') // ponytail: a forged 'fatal' just costs the user a respawn
  }
  w.onerror = (e) => {
    if (waiter) waiter({ type: 'fatal', error: e.message || 'worker error' })
    else if (worker === w) discard()
  }
  ready = request({ type: 'init', packages }, ['ready'], undefined).then((m) => {
    if (m.type === 'ready') return undefined
    discard()
    return m.error
  })
  return ready
}

async function exec(code: string, mode: Mode, retried = false): Promise<SandboxResult> {
  const err = await boot()
  if (err) return { ok: false, error: err }
  const id = ++seq
  let timer: ReturnType<typeof setTimeout> | undefined
  // The timer starts on 'started', so package loading is never charged to user code.
  const m = await request({ type: 'run', id, code, mode }, ['started', 'result', 'error'], id, () => {
    timer ??= setTimeout(() => waiter?.({ type: 'timeout' }), KILL_MS)
  })
  clearTimeout(timer)
  if (m.type === 'result') return { ok: true, result: m.result, stdout: m.stdout!, figures: m.figures!, ms: m.ms! }
  if (m.type === 'error') {
    if (!m.needsRespawn || retried) return { ok: false, error: m.error! }
    packages = [...new Set([...packages, ...m.needsRespawn])]
    discard()
    return exec(code, mode, true)
  }
  discard() // fatal or timeout: the worker is gone, the next call respawns
  return { ok: false, error: m.type === 'timeout' ? 'timeout' : m.error! }
}

export const warm = (): Promise<void> => (tail = tail.then(boot)).then(() => undefined)

export function run(code: string, opts: { mode?: Mode; latestWins?: boolean } = {}): Promise<SandboxResult> {
  return new Promise((resolve) => {
    const job = { latest: !!opts.latestWins, resolve }
    // latestWins supersedes older jobs that are still waiting (never the one running).
    if (job.latest) for (const j of pending) if (j.latest) { pending.delete(j); j.resolve({ ok: false, error: 'superseded' }) }
    pending.add(job)
    tail = tail.then(async () => {
      if (pending.delete(job)) resolve(await exec(code, opts.mode ?? 'solve'))
    })
  })
}

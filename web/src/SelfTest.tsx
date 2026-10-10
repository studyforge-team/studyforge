import { useEffect, useState } from 'react'
import { readyS, selftest } from '@/sandbox/selftest'

type Row = Awaited<ReturnType<typeof selftest>>[number]

export default function SelfTest() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [done, setDone] = useState(0)
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    const t0 = Date.now()
    const tick = setInterval(() => setSecs(Math.round((Date.now() - t0) / 1000)), 1000)
    void selftest(setDone).then((r) => {
      clearInterval(tick)
      setSecs(Math.round((Date.now() - t0) / 1000))
      Object.assign(window, { __selftest: r })
      setRows(r)
    })
    return () => clearInterval(tick)
  }, [])
  if (!rows) {
    return (
      <main className="p-4">
        <p>{done ? `Running sandbox self-test: ${done} of 35 done` : 'Downloading and starting Python (first run is slow; keep this tab open)'}…</p>
        <p className="mt-2 text-sm text-muted-foreground">{secs} s elapsed{readyS ? ` · Python ready in ${readyS} s` : ''}. The whole test takes 1–3 minutes.</p>
      </main>
    )
  }
  return (
    <main className="p-4">
      <h1 className="text-xl font-bold">Sandbox self-test: {rows.filter((r) => r.pass).length}/{rows.length} passed</h1>
      <p className="mt-2 font-medium">Python ready in {readyS} s · whole test {secs} s</p>
      <table className="mt-4 text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.name}>
              <td className="pr-4">{r.pass ? 'PASS' : 'FAIL'}</td>
              <td className="pr-4">{r.name}</td>
              <td>{r.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  )
}

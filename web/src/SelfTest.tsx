import { useEffect, useState } from 'react'
import { selftest } from '@/sandbox/selftest'

type Row = Awaited<ReturnType<typeof selftest>>[number]

export default function SelfTest() {
  const [rows, setRows] = useState<Row[] | null>(null)
  useEffect(() => {
    void selftest().then((r) => {
      Object.assign(window, { __selftest: r })
      setRows(r)
    })
  }, [])
  if (!rows) return <p className="p-4">Running sandbox self-test (first run downloads Python)...</p>
  return (
    <main className="p-4">
      <h1 className="text-xl font-bold">Sandbox self-test: {rows.filter((r) => r.pass).length}/{rows.length} passed</h1>
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

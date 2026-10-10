import { lazy, Suspense, useEffect, useState } from 'react'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Solve from './pages/Solve'

const SelfTest = lazy(() => import('./SelfTest'))
const ChemLab = lazy(() => import('./pages/ChemLab')) // keeps the sandbox page out of the main chunk

export default function App() {
  const [hash, setHash] = useState(location.hash) // ponytail: hash routing, no router library
  useEffect(() => {
    const on = () => setHash(location.hash)
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])
  if (location.search.includes('selftest')) {
    return (
      <Suspense fallback={null}>
        <SelfTest />
      </Suspense>
    )
  }
  return <Shell hash={hash}>
      {hash === '#solve' ? <Solve /> : hash.startsWith('#chemlab') ? (
        <Suspense fallback={<p role="status" className="mx-auto max-w-3xl px-4 py-6 text-sm text-muted-foreground">Loading ChemLab…</p>}><ChemLab key={hash} /></Suspense>
      ) : <Dashboard />}
    </Shell>
}

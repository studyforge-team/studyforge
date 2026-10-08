import { lazy, Suspense, useEffect, useState } from 'react'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Solve from './pages/Solve'

const SelfTest = lazy(() => import('./SelfTest'))

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
  return <Shell hash={hash}>{hash === '#solve' ? <Solve /> : <Dashboard />}</Shell>
}

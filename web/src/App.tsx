import { lazy, Suspense, useEffect, useState } from 'react'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Solve from './pages/Solve'

const SelfTest = lazy(() => import('./SelfTest'))
const History = lazy(() => import('./pages/History'))
const OA = lazy(() => import('./pages/OA'))
const InterviewBank = lazy(() => import('./pages/InterviewBank'))

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
  return (
    <Shell hash={hash}>
      {hash.startsWith('#oa') ? (
        <Suspense fallback={null}>
          <OA />
        </Suspense>
      ) : hash.startsWith('#interview') ? (
        <Suspense fallback={null}>
          <InterviewBank />
        </Suspense>
      ) : hash.startsWith('#history') ? (
        <Suspense fallback={null}>
          <History />
        </Suspense>
      ) : hash === '#solve' ? (
        <Solve />
      ) : (
        <Dashboard />
      )}
    </Shell>
  )
}

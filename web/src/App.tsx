import { lazy, Suspense, useEffect, useState } from 'react'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Quiz from './pages/Quiz'
import Solve from './pages/Solve'
import InterviewBank from './pages/InterviewBank'
import OA from './pages/OA'
import TimeToFinish from './pages/TimeToFinish'

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

  return (
    <Shell hash={hash}>
      {hash === '#solve' ? (
        <Solve />
      ) : hash === '#quiz' ? (
        <Quiz />
      ) : hash === '#oa' ? (
        <OA />
      ) : hash === '#interview-bank' ? (
        <InterviewBank />
      ) : hash === '#time-to-finish' ? (
        <TimeToFinish />
      ) : hash.startsWith('#chemlab') ? (
        <Suspense
          fallback={
            <p role="status" className="mx-auto max-w-3xl px-4 py-6 text-sm text-muted-foreground">
              Loading ChemLabâ€¦
            </p>
          }
        >
          <ChemLab key={hash} />
        </Suspense>
      ) : (
        <Dashboard />
      )}
    </Shell>
  )
}

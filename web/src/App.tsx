import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
import Shell from './components/Shell'
import Dashboard from './pages/Dashboard'
import Quiz from './pages/Quiz'
import Solve from './pages/Solve'
import InterviewBank from './pages/InterviewBank'
import OA from './pages/OA'
import PYQPredictor from './pages/PYQPredictor'
import TimeToFinish from './pages/TimeToFinish'
import Privacy from './pages/Privacy'

// ponytail: one boundary around the page; shows a fixed message, never the error
class Boundary extends Component<{ children: ReactNode }, { bad: boolean }> {
  state = { bad: false }
  static getDerivedStateFromError() { return { bad: true } }
  render() {
    return this.state.bad
      ? <main className="mx-auto max-w-3xl px-4 py-6"><p role="alert" className="text-sm font-medium text-destructive">This page hit a problem. Reload to try again.</p><button type="button" className="mt-3 min-h-11 rounded-lg border px-4" onClick={() => location.reload()}>Reload</button></main>
      : this.props.children
  }
}

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
      <Boundary key={hash}>
      {hash === '#solve' ? (
        <Solve />
      ) : hash === '#quiz' ? (
        <Quiz />
      ) : hash === '#oa' ? (
        <OA />
      ) : hash === '#interview-bank' ? (
        <InterviewBank />
      ) : hash === '#pyq-predictor' ? (
        <PYQPredictor />
      ) : hash === '#privacy' ? (
        <Privacy />
      ) : hash === '#time-to-finish' ? (
        <TimeToFinish />
      ) : hash.startsWith('#chemlab') ? (
        <Suspense
          fallback={
            <p role="status" className="mx-auto max-w-3xl px-4 py-6 text-sm text-muted-foreground">
              Loading ChemLab…
            </p>
          }
        >
          <ChemLab key={hash} />
        </Suspense>
      ) : (
        <Dashboard />
      )}
      </Boundary>
    </Shell>
  )
}

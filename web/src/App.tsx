import { lazy, Suspense } from 'react'
import Solve from './pages/Solve'

const SelfTest = lazy(() => import('./SelfTest'))

export default function App() {
  if (location.search.includes('selftest')) {
    return (
      <Suspense fallback={null}>
        <SelfTest />
      </Suspense>
    )
  }
  return <Solve />
}

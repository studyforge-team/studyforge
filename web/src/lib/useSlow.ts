import { useEffect, useState } from 'react'

// True once `pending` has lasted `ms` (the free Render server can take about a minute to wake).
export function useSlow(pending: boolean, ms = 4000): boolean {
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (!pending) return
    const t = setTimeout(() => setSlow(true), ms)
    return () => { clearTimeout(t); setSlow(false) }
  }, [pending, ms])
  return pending && slow
}

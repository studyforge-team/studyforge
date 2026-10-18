import { useState } from 'react'
import { Button } from '@/components/ui/button'

// S5: the student checks (and fixes) what the machine read before anything is solved.
export function ConfirmQuestion({ text, low, onSolve, onDismiss }: {
  text: string; low?: boolean; onSolve: (text: string) => void; onDismiss: () => void
}) {
  const [v, setV] = useState(text)
  return (
    <section aria-labelledby="cq-h" className="mt-3 rounded-lg border-2 border-warn-line bg-warn-bg p-4 text-sm">
      <h2 id="cq-h" className="font-medium">Check the question before solving</h2>
      <label htmlFor="cq" className="mt-2 block font-medium">Question as we read it</label>
      <textarea
        id="cq" rows={5} value={v} onChange={(e) => setV(e.target.value)}
        className="mt-1 w-full rounded-lg border border-input bg-background p-3 text-base"
      />
      {!text.trim() && <p className="mt-2 text-warn">We couldn't read it — type the question.</p>}
      {low && <p className="mt-2 text-warn">Check this carefully — the reading may be wrong.</p>}
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <Button className="w-full sm:w-auto" disabled={!v.trim()} onClick={() => onSolve(v)}>Solve this question</Button>
        <Button variant="outline" className="w-full sm:w-auto" onClick={onDismiss}>Type it myself</Button>
      </div>
    </section>
  )
}

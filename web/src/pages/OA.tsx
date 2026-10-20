import { useState, useEffect } from 'react'
import CompanyOA from '@/components/CompanyOA'

type Problem = {
  id: string
  title: string
  difficulty: 'Easy' | 'Medium' | 'Hard'
  category: string
  description: string
}

const CODING_PROBLEMS: Problem[] = [
  {
    id: 'cstr-residence-time',
    title: 'Calculate CSTR Residence Time Distribution',
    difficulty: 'Easy',
    category: 'Reaction Engineering',
    description: 'Implement a function to compute E(t) curve from tracer concentration data.',
  },
  {
    id: 'antoine-vapor-pressure',
    title: 'Antoine Equation Vapor Pressure Solver',
    difficulty: 'Easy',
    category: 'Thermodynamics',
    description: 'Calculate saturation pressure given Antoine coefficients A, B, C and temperature T.',
  },
  {
    id: 'heat-exchanger-lmtd',
    title: 'Counter-Current Heat Exchanger LMTD',
    difficulty: 'Medium',
    category: 'Heat Transfer',
    description: 'Compute log-mean temperature difference and overall heat transfer area.',
  },
  {
    id: 'distillation-mccabe-thiele',
    title: 'McCabe-Thiele Minimum Stages Calculator',
    difficulty: 'Hard',
    category: 'Mass Transfer',
    description: 'Determine the number of theoretical stages given relative volatility and reflux ratio.',
  },
]

export default function OA() {
  const getInitial = () => {
    const hash = window.location.hash
    const m = hash.match(/^#oa\?company=([^&]+)/)
    return m ? m[1] : undefined
  }

  const initialCompany = getInitial()
  const [tab, setTab] = useState<'coding' | 'company'>(initialCompany ? 'company' : 'coding')
  const [selectedInitial, setSelectedInitial] = useState<string | undefined>(initialCompany)

  useEffect(() => {
    const onHashChange = () => {
      const comp = getInitial()
      if (comp) {
        setSelectedInitial(comp)
        setTab('company')
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      {/* 2-tab switch: Coding vs Company OA */}
      <div className="mb-6 flex border-b">
        <button
          type="button"
          onClick={() => setTab('coding')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            tab === 'coding'
              ? 'border-primary font-semibold text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Coding
        </button>
        <button
          type="button"
          onClick={() => setTab('company')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            tab === 'company'
              ? 'border-primary font-semibold text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Company OA
        </button>
      </div>

      {tab === 'coding' ? (
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Coding Practice</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              Core numerical and chemical computing challenges commonly tested in engineering online assessments.
            </p>
          </div>

          <div className="divide-y rounded-lg border bg-card">
            {CODING_PROBLEMS.map((prob) => (
              <div key={prob.id} className="p-4 hover:bg-muted/10">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">{prob.title}</h3>
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                      prob.difficulty === 'Easy'
                        ? 'bg-green-100 text-green-700'
                        : prob.difficulty === 'Medium'
                        ? 'bg-amber-100 text-amber-700'
                        : 'bg-red-100 text-red-700'
                    }`}
                  >
                    {prob.difficulty}
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{prob.description}</p>
                <div className="mt-2 text-[11px] text-muted-foreground/75 font-medium">
                  Category: {prob.category}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <CompanyOA initial={selectedInitial} />
      )}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { run } from '@/sandbox/client'
import CompanyOA from '@/components/CompanyOA'

type Problem = {
  id: string
  title: string
  difficulty: string
  description: string
  starter: string
  tests: { input: string; expected: unknown }[]
  anyOrder?: boolean // a list answer counts in any order (e.g. the two indices)
}

const problems: Problem[] = [
  {
    id: 'two-sum',
    anyOrder: true,
    title: '1. Two Sum',
    difficulty: 'Easy',
    description:
      'Implement two_sum(nums, target). Return the indices of two distinct elements whose sum equals target, in any order. Assume exactly one solution exists.',
    starter: `def two_sum(nums, target):
    # Return the two indices
    pass

result = two_sum([2, 7, 11, 15], 9)`,
    tests: [
      { input: 'two_sum([2, 7, 11, 15], 9)', expected: [0, 1] },
      { input: 'two_sum([3, 2, 4], 6)', expected: [1, 2] },
      { input: 'two_sum([3, 3], 6)', expected: [0, 1] },
    ],
  },
  {
    id: 'palindrome',
    title: '2. Valid Palindrome',
    difficulty: 'Easy',
    description:
      'Implement is_palindrome(s). Ignore spaces, punctuation, and letter case. Return True if the remaining string reads the same forwards and backwards.',
    starter: `def is_palindrome(s):
    # Return True or False
    pass

result = is_palindrome("A man, a plan, a canal: Panama")`,
    tests: [
      { input: 'is_palindrome("A man, a plan, a canal: Panama")', expected: true },
      { input: 'is_palindrome("race a car")', expected: false },
      { input: 'is_palindrome(" ")', expected: true },
    ],
  },
  {
    id: 'first-unique',
    title: '3. First Non-Repeating Character',
    difficulty: 'Easy',
    description:
      'Implement first_unique(s). Return the first character that appears exactly once, or None if every character repeats.',
    starter: `def first_unique(s):
    # Return a character or None
    pass

result = first_unique("swiss")`,
    tests: [
      { input: 'first_unique("swiss")', expected: 'w' },
      { input: 'first_unique("aabb")', expected: null },
      { input: 'first_unique("leetcode")', expected: 'l' },
    ],
  },
]

function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (Array.isArray(a) && Array.isArray(b)) {
    return a.length === b.length && a.every((value, i) => sameValue(value, b[i]))
  }
  return false
}

function sorted(v: unknown): unknown {
  return Array.isArray(v) ? [...v].sort((x, y) => String(x).localeCompare(String(y), undefined, { numeric: true })) : v
}

// The sandbox returns the last 600 characters of a Python traceback; show only the error line.
function shortError(error: string): string {
  if (error === 'timeout') return 'took longer than 10 s (an infinite loop?)'
  const lines = error.split('\n').map((l) => l.trim()).filter(Boolean)
  return lines.at(-1) ?? error
}

// The starter ends with an example call (`result = two_sum([...], 9)`). Drop only that
// last line if it is a plain call, so it isn't re-run before every test; any other use
// of a `result` variable in the student's code is left alone.
function withoutExampleCall(code: string): string {
  const lines = code.replace(/\s+$/, '').split('\n')
  return /^result\s*=\s*[A-Za-z_]\w*\(.*\)\s*$/.test(lines.at(-1) ?? '') ? lines.slice(0, -1).join('\n') : code
}

const STORE = 'studyforge.oa.v1' // per-browser drafts and results, so leaving the page keeps work

type Saved = { codes: Record<string, string>; status: Record<string, string> }

function load(): Saved {
  try {
    const raw = localStorage.getItem(STORE)
    const v: unknown = raw ? JSON.parse(raw) : {}
    const strings = (o: unknown): Record<string, string> =>
      o && typeof o === 'object'
        ? Object.fromEntries(Object.entries(o).filter(([, x]) => typeof x === 'string'))
        : {}
    const obj = (v && typeof v === 'object' ? v : {}) as Record<string, unknown>
    return { codes: strings(obj.codes), status: strings(obj.status) }
  } catch {
    return { codes: {}, status: {} }
  }
}

function CodingOA() {
  const [selected, setSelected] = useState(0)
  const [codes, setCodes] = useState(() => {
    const saved = load().codes
    return problems.map((p) => saved[p.id] ?? p.starter)
  })
  const [status, setStatus] = useState<Record<string, string>>(() => load().status)
  const [fails, setFails] = useState<Record<string, string[]>>({}) // failed-test detail, this session only
  const [running, setRunning] = useState<string | null>(null) // id of the problem being run
  const alive = useRef(true)
  const latest = useRef(codes) // the code as it is now, to spot edits made during a run
  useEffect(() => {
    latest.current = codes
  }, [codes])

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false // stop an unfinished run from queueing more tests after leaving
    }
  }, [])

  useEffect(() => {
    try {
      const before = load().status // a run in progress keeps the last finished result saved
      const done = Object.fromEntries(
        Object.entries(status).flatMap(([k, v]) =>
          v.startsWith('Running') ? (before[k] ? [[k, before[k]]] : []) : [[k, v]],
        ),
      )
      localStorage.setItem(
        STORE,
        JSON.stringify({ codes: Object.fromEntries(problems.map((p, i) => [p.id, codes[i]])), status: done }),
      )
    } catch {
      // storage blocked (private window): the page still works, drafts just aren't kept
    }
  }, [codes, status])

  const problem = problems[selected]

  async function submit() {
    if (running) return
    const target = problem
    const index = selected
    const ranCode = codes[index]
    const source = withoutExampleCall(ranCode)
    setRunning(target.id)
    setStatus((old) => ({ ...old, [target.id]: 'Running sample tests…' }))

    try {
      let passed = 0
      let errors = 0
      let firstError = ''
      const failed: string[] = []
      const show = (v: unknown) => JSON.stringify(v) ?? String(v)
      for (const [i, test] of target.tests.entries()) {
        if (!alive.current) return
        const response = await run(`${source}\nresult = ${test.input}`, { mode: 'solve' })
        if (!response.ok) {
          errors += 1
          firstError ||= `test ${i + 1}: ${shortError(response.error)}`
          failed.push(`${test.input} -> error: ${shortError(response.error)} (expected ${show(test.expected)})`)
          if (response.error === 'timeout' || response.error === 'sandbox failed to start') {
            errors += target.tests.length - i - 1 // an infinite loop or a dead sandbox fails the rest too
            break
          }
          continue
        }
        const ok = target.anyOrder
          ? sameValue(sorted(response.result), sorted(test.expected))
          : sameValue(response.result, test.expected)
        if (ok) passed += 1
        else failed.push(`${test.input} -> expected ${show(test.expected)}, got ${show(response.result)}`)
      }
      if (!alive.current) return
      if (latest.current[index] !== ranCode) {
        setStatus((old) => ({ ...old, [target.id]: 'Code changed during the run. Run the tests again.' }))
        return
      }
      const total = target.tests.length
      setFails((old) => ({ ...old, [target.id]: failed }))
      setStatus((old) => ({
        ...old,
        [target.id]:
          errors === total // the code never ran (syntax error, import error, ...)
            ? `Execution error: ${firstError.replace(/^test \d+: /, '')}`
            : firstError
              ? `${passed}/${total} sample tests passed. Error in ${firstError}`
              : `${passed}/${total} sample tests passed`,
      }))
    } finally {
      if (alive.current) setRunning(null)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:py-8">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Practice
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">OA Prep</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Practise Python coding problems and check your solution against sample tests.
      </p>

      <div role="group" className="mt-6 flex flex-wrap gap-2" aria-label="Choose a problem">
        {problems.map((p, i) => (
          <Button
            key={p.id}
            variant={selected === i ? 'default' : 'outline'}
            aria-pressed={selected === i}
            onClick={() => setSelected(i)}
          >
            {p.title}
          </Button>
        ))}
      </div>

      <section className="mt-5 rounded-lg border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-semibold">{problem.title}</h2>
          <span className="rounded-full bg-tint px-3 py-1 text-xs font-medium text-primary">
            {problem.difficulty}
          </span>
        </div>
        <p className="mt-3 text-sm leading-6">{problem.description}</p>

        <label
          htmlFor="oa-python"
          className="mt-5 block text-sm font-medium"
        >
          Your Python solution
        </label>
        <textarea
          id="oa-python"
          spellCheck={false}
          value={codes[selected]}
          onChange={(event) =>
            {
              setCodes((old) =>
                old.map((code, i) => (i === selected ? event.target.value : code)),
              )
              if (running !== problem.id) {
                setStatus((old) => {
                  const next = { ...old }
                  delete next[problem.id] // the old result no longer matches this code
                  return next
                })
              }
            }
          }
          className="mt-2 min-h-80 w-full resize-y rounded-lg border bg-background p-4 font-mono text-sm leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => void submit()} disabled={running !== null}>
            {running === problem.id ? 'Running…' : 'Run sample tests'}
          </Button>
          <p
            role="status"
            aria-live="polite"
            className="text-sm text-muted-foreground"
          >
            {running && running !== problem.id
              ? 'Another problem is still running its tests…'
              : (status[problem.id] ?? 'No submission yet.')}
          </p>
          {status[problem.id] && fails[problem.id]?.length ? (
            <ul className="w-full space-y-1 font-mono text-xs text-destructive">
              {fails[problem.id].map((f, i) => <li key={i} className="break-all">{f}</li>)}
            </ul>
          ) : null}
        </div>
      </section>

      <p className="mt-4 text-xs leading-5 text-muted-foreground">
        Sample tests are visible in this client-side practice page. They are not
        hidden tests or a security boundary.
      </p>
    </main>
  )
}

const TAB = 'min-h-11 border-b-2 px-4 py-2 text-sm font-medium'
const companyFromHash = () => /^#oa\?company=([^&]+)/.exec(location.hash)?.[1]

export default function OA() {
  const [company, setCompany] = useState(companyFromHash())
  const [tab, setTab] = useState<'coding' | 'company'>(company ? 'company' : 'coding')
  useEffect(() => {
    const onHash = () => {
      const c = companyFromHash()
      if (c) { setCompany(c); setTab('company') }
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  return (
    <>
      <div role="group" aria-label="OA type" className="mx-auto flex max-w-4xl gap-2 border-b px-4 pt-4">
        {([['coding', 'Coding'], ['company', 'Company OA']] as const).map(([k, label]) => (
          <button key={k} type="button" aria-pressed={tab === k} onClick={() => setTab(k)}
            className={`${TAB} ${tab === k ? 'border-primary text-primary' : 'border-transparent text-muted-foreground'}`}>{label}</button>
        ))}
      </div>
      {tab === 'coding' ? <CodingOA /> : <main className="mx-auto max-w-4xl px-4 py-6 sm:py-8"><CompanyOA initial={company} /></main>}
    </>
  )
}

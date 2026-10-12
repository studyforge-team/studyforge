import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { run } from '@/sandbox/client'

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
  const lines = error.split('\n').map((l) => l.trim()).filter(Boolean)
  return lines.at(-1) ?? error
}

export default function OA() {
  const [selected, setSelected] = useState(0)
  const [codes, setCodes] = useState(() => problems.map((p) => p.starter))
  const [status, setStatus] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)

  const problem = problems[selected]

  async function submit() {
    setRunning(true)
    setStatus((old) => ({ ...old, [problem.id]: 'Running sample tests…' }))

    try {
      const results: boolean[] = []

      for (const test of problem.tests) {
        const code = `${codes[selected]}\nresult = ${test.input}`
        const response = await run(code, { mode: 'solve' })

        if (!response.ok) {
          setStatus((old) => ({
            ...old,
            [problem.id]: `Execution error: ${shortError(response.error)}`,
          }))
          return
        }

        results.push(
          problem.anyOrder
            ? sameValue(sorted(response.result), sorted(test.expected))
            : sameValue(response.result, test.expected),
        )
      }

      const passed = results.filter(Boolean).length
      setStatus((old) => ({
        ...old,
        [problem.id]: `${passed}/${results.length} sample tests passed`,
      }))
    } finally {
      setRunning(false)
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
            setCodes((old) =>
              old.map((code, i) => (i === selected ? event.target.value : code)),
            )
          }
          className="mt-2 min-h-80 w-full resize-y rounded-lg border bg-background p-4 font-mono text-sm leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={() => void submit()} disabled={running}>
            {running ? 'Running…' : 'Run sample tests'}
          </Button>
          <p
            role="status"
            aria-live="polite"
            className="text-sm text-muted-foreground"
          >
            {status[problem.id] ?? 'No submission yet.'}
          </p>
        </div>
      </section>

      <p className="mt-4 text-xs leading-5 text-muted-foreground">
        Sample tests are visible in this client-side practice page. They are not
        hidden tests or a security boundary.
      </p>
    </main>
  )
}

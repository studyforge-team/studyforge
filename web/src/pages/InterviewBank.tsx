import { useState } from 'react'

type Question = {
  id: number
  company: string
  category: string
  difficulty: 'Easy' | 'Medium' | 'Hard'
  question: string
  answer: string
}

const questions: Question[] = [
  {
    id: 1,
    company: 'Google',
    category: 'Data Structures',
    difficulty: 'Medium',
    question: 'How would you detect a cycle in a linked list?',
    answer: 'Use Floyd’s tortoise-and-hare algorithm. Move one pointer by one node and another by two nodes. If they meet, a cycle exists. Time: O(n); extra space: O(1).',
  },
  {
    id: 2,
    company: 'Google',
    category: 'Algorithms',
    difficulty: 'Medium',
    question: 'What is the time complexity of binary search?',
    answer: 'O(log n) time, because the search interval is halved at every step. An iterative implementation uses O(1) extra space.',
  },
  {
    id: 3,
    company: 'Microsoft',
    category: 'Data Structures',
    difficulty: 'Easy',
    question: 'What is the difference between a stack and a queue?',
    answer: 'A stack follows LIFO (last in, first out); a queue follows FIFO (first in, first out).',
  },
  {
    id: 4,
    company: 'Microsoft',
    category: 'Algorithms',
    difficulty: 'Medium',
    question: 'How does merge sort work?',
    answer: 'It divides the array into halves, recursively sorts each half, and merges the sorted halves. Time: O(n log n); typical auxiliary space: O(n).',
  },
  {
    id: 5,
    company: 'Amazon',
    category: 'Arrays',
    difficulty: 'Easy',
    question: 'How can you find two numbers in an array that add up to a target?',
    answer: 'Use a hash map to store previously seen values. For each number x, check whether target − x is already stored. Expected time: O(n), extra space: O(n).',
  },
  {
    id: 6,
    company: 'Amazon',
    category: 'Algorithms',
    difficulty: 'Hard',
    question: 'What is the difference between breadth-first search and depth-first search?',
    answer: 'BFS explores level by level using a queue; DFS explores a path deeply before backtracking, commonly using a stack or recursion. Both run in O(V + E) time on an adjacency-list graph.',
  },
]

const field = 'min-h-11 rounded-lg border border-input bg-background px-3 py-2 text-base'

export default function InterviewBank() {
  const [company, setCompany] = useState('All companies')
  const [revealed, setRevealed] = useState<number[]>([])

  const visibleQuestions = questions.filter(
    (item) => company === 'All companies' || item.company === company,
  )

  function toggleAnswer(id: number) {
    setRevealed((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id],
    )
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <header>
        <p className="text-sm text-muted-foreground">Practice · Interview preparation</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Interview Bank</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Practice sample technical questions and reveal answers when you’re ready.
        </p>
      </header>

      <section className="mt-6 rounded-lg border bg-card p-4">
        <label htmlFor="company-filter" className="block text-sm font-medium">
          Filter by company
        </label>
        <select
          id="company-filter"
          aria-label="Filter by company"
          className={`${field} mt-2 w-full sm:max-w-xs`}
          value={company}
          onChange={(event) => setCompany(event.target.value)}
        >
          <option>All companies</option>
          <option>Google</option>
          <option>Microsoft</option>
          <option>Amazon</option>
        </select>
        <p className="mt-2 text-sm text-muted-foreground" aria-live="polite">
          {visibleQuestions.length} practice questions
        </p>
      </section>

      <ul aria-label="Practice questions" className="mt-4 space-y-3">
        {visibleQuestions.map((item) => {
          const isRevealed = revealed.includes(item.id)

          return (
            <li key={item.id} className="rounded-lg border bg-card p-4 sm:p-5">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span className="rounded-full border px-2 py-1">{item.company}</span>
                <span>{item.category}</span>
                <span>·</span>
                <span>{item.difficulty}</span>
              </div>
              <h2 className="mt-3 text-base font-semibold">{item.question}</h2>

              {isRevealed && (
                <div className="mt-4 rounded-md bg-muted p-3 text-sm">
                  <p className="font-medium">Answer:</p>
                  <p className="mt-1 leading-6">{item.answer}</p>
                </div>
              )}

              <button
                type="button"
                className="mt-4 inline-flex min-h-11 items-center rounded-md border px-4 text-sm font-medium hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-expanded={isRevealed}
                onClick={() => toggleAnswer(item.id)}
              >
                {isRevealed ? 'Hide answer' : 'Show answer'}
              </button>
            </li>
          )
        })}
      </ul>
    </main>
  )
}

import { useState } from 'react'

const TOPICS = [
  { name: 'Binary search', pattern: /\bbinary\s+search\b/i, question: 'Explain binary search and analyze its time complexity.' },
  { name: 'Arrays', pattern: /\barrays?\b/i, question: 'Describe an array operation and analyze its time and space complexity.' },
  { name: 'Linked lists', pattern: /\blinked\s+lists?\b/i, question: 'Explain how insertion and deletion work in a linked list.' },
  { name: 'Stacks and queues', pattern: /\bstacks?\b|\bqueues?\b/i, question: 'Compare stack and queue operations with suitable examples.' },
  { name: 'Trees', pattern: /\bbinary\s+trees?\b|\btrees?\b/i, question: 'Explain a tree traversal and state its complexity.' },
  { name: 'Graphs', pattern: /\bgraphs?\b|\bbfs\b|\bdfs\b/i, question: 'Compare breadth-first and depth-first graph traversal.' },
  { name: 'Sorting', pattern: /\bsort(?:ing)?\b|\bmerge\s+sort\b|\bquick\s+sort\b/i, question: 'Explain a sorting algorithm and analyze its complexity.' },
  { name: 'Dynamic programming', pattern: /\bdynamic\s+programming\b|\btabulation\b|\bmemoization\b/i, question: 'Describe a dynamic programming recurrence and its base cases.' },
  { name: 'Recursion', pattern: /\brecursion\b|\brecursive\b/i, question: 'Explain the base case and recursive step of an algorithm.' },
  { name: 'Hashing', pattern: /\bhash(?:ing|map| table| tables)?\b/i, question: 'Explain collision handling in a hash table.' },
] as const

const field = 'mt-2 min-h-11 w-full rounded-lg border border-input bg-background px-3 py-2 text-base'

type Frequency = { topic: string; papers: number; question: string }

export default function PYQPredictor() {
  const [papers, setPapers] = useState(['', '', ''])
  const [error, setError] = useState('')
  const [frequencies, setFrequencies] = useState<Frequency[] | null>(null)

  function updatePaper(index: number, value: string) {
    setPapers((current) =>
      current.map((paper, i) => (i === index ? value : paper)),
    )
  }

  function predict() {
    setError('')
    setFrequencies(null)

    if (papers.some((paper) => !paper.trim())) {
      setError('Please enter text from all three past papers before predicting topics.')
      return
    }

    const results = TOPICS.map((topic) => ({
      topic: topic.name,
      papers: papers.filter((paper) => topic.pattern.test(paper)).length,
      question: topic.question,
    }))
      .filter((item) => item.papers > 0)
      .sort((a, b) => b.papers - a.papers || a.topic.localeCompare(b.topic))

    if (results.length === 0) {
      setError('No supported topics were detected. Try pasting text about common data structures or algorithms.')
      return
    }

    setFrequencies(results)
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:py-8">
      <header>
        <p className="text-sm text-muted-foreground">Study tools · Exam preparation</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">PYQ Predictor</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Compare three past papers to find recurring topics and build a focused practice set.
        </p>
      </header>

      <section className="mt-6 space-y-4 rounded-lg border bg-card p-4 sm:p-5">
        {papers.map((paper, index) => (
          <div key={index}>
            <label htmlFor={`past-paper-${index + 1}`} className="block text-sm font-medium">
              Past paper {index + 1}
            </label>
            <textarea
              id={`past-paper-${index + 1}`}
              aria-label={`Past paper ${index + 1}`}
              className={`${field} min-h-28`}
              placeholder="Paste the question text or topic headings here…"
              value={paper}
              onChange={(event) => updatePaper(index, event.target.value)}
            />
          </div>
        ))}

        <button
          type="button"
          className="inline-flex min-h-11 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onClick={predict}
        >
          Predict topics
        </button>

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </section>

      {frequencies && (
        <section className="mt-6 space-y-6">
          <div>
            <h2 className="text-lg font-semibold">Topic frequency</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Count = number of supplied papers mentioning the topic, not the number of individual questions.
            </p>
            <div className="mt-3 overflow-x-auto rounded-lg border">
              <table aria-label="Topic frequency" className="w-full text-left text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th scope="col" className="px-3 py-3 font-medium">Topic</th>
                    <th scope="col" className="px-3 py-3 font-medium">Papers mentioning topic</th>
                  </tr>
                </thead>
                <tbody>
                  {frequencies.map((item) => (
                    <tr key={item.topic} className="border-t">
                      <td className="px-3 py-3">{item.topic}</td>
                      <td className="px-3 py-3 tabular-nums">{item.papers} / 3</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="text-lg font-semibold">Likely practice paper</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Suggested practice questions ranked by how many of these papers mention each topic.
            </p>
            <ol className="mt-3 space-y-3">
              {frequencies.slice(0, 5).map((item, index) => (
                <li key={item.topic} className="rounded-lg border bg-card p-4">
                  <p className="text-xs text-muted-foreground">
                    Question {index + 1} · {item.topic} · {item.papers} of 3 papers
                  </p>
                  <p className="mt-2 text-sm font-medium">{item.question}</p>
                </li>
              ))}
            </ol>
          </div>

          <p className="rounded-lg border p-3 text-sm text-muted-foreground">
            Estimate only — these suggestions are based on a small sample of three papers and a limited topic dictionary. They are not guaranteed exam questions. Topics absent from this sample may still appear in your exam.
          </p>
        </section>
      )}
    </main>
  )
}

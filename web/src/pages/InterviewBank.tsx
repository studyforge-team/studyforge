import { useState } from 'react'
import ChemInterview from '@/components/ChemInterview'

type CSQuestion = {
  id: string
  title: string
  category: 'Algorithms' | 'System Design' | 'Operating Systems' | 'Databases'
  question: string
  keyPoints: string[]
}

const CS_QUESTIONS: CSQuestion[] = [
  {
    id: 'cs-lru-cache',
    title: 'LRU Cache Design',
    category: 'Algorithms',
    question: 'How would you design and implement a Least Recently Used (LRU) Cache with O(1) get and put operations?',
    keyPoints: [
      'Use a doubly linked list combined with a hash map.',
      'Hash map stores key to node pointers for O(1) access.',
      'Doubly linked list maintains access order: move accessed node to head, evict from tail.',
    ],
  },
  {
    id: 'cs-rate-limiter',
    title: 'Distributed Rate Limiter',
    category: 'System Design',
    question: 'Describe how to architect a scalable rate limiter for an API gateway serving millions of requests per second.',
    keyPoints: [
      'Token bucket or sliding window log algorithms.',
      'Centralized fast cache (Redis) with atomic increments (INCR / Lua scripts).',
      'Handle race conditions and clock skew across distributed servers.',
    ],
  },
  {
    id: 'cs-process-thread',
    title: 'Process vs Thread & Context Switching',
    category: 'Operating Systems',
    question: 'What is the architectural difference between a process and a thread, and why is thread context switching cheaper?',
    keyPoints: [
      'Processes have isolated virtual memory spaces and descriptors; threads share the process heap, code, and address space.',
      'Thread context switch does not require flushing TLB or swapping page tables.',
    ],
  },
  {
    id: 'cs-acid-isolation',
    title: 'ACID Properties & Transaction Isolation Levels',
    category: 'Databases',
    question: 'Explain the four standard SQL transaction isolation levels and the anomalies they prevent.',
    keyPoints: [
      'Read Uncommitted (dirty reads allowed).',
      'Read Committed (prevents dirty reads, allows non-repeatable reads).',
      'Repeatable Read (prevents non-repeatable reads, phantom reads possible depending on MVCC/locking).',
      'Serializable (strict serial ordering, prevents phantom reads).',
    ],
  },
]

export default function InterviewBank() {
  const [field, setField] = useState<'Chemical' | 'Computer science'>('Chemical')

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      {/* Field switch: Chemical vs Computer science */}
      <div className="mb-6 flex border-b">
        <button
          type="button"
          onClick={() => setField('Chemical')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            field === 'Chemical'
              ? 'border-primary font-semibold text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Chemical
        </button>
        <button
          type="button"
          onClick={() => setField('Computer science')}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            field === 'Computer science'
              ? 'border-primary font-semibold text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          Computer science
        </button>
      </div>

      {field === 'Chemical' ? (
        <ChemInterview />
      ) : (
        <div className="space-y-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Computer Science Interview Bank</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              Fundamental technical interview questions across data structures, system design, and systems engineering.
            </p>
          </div>

          <div className="space-y-4">
            {CS_QUESTIONS.map((q) => (
              <div key={q.id} className="rounded-lg border bg-card p-4 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold">{q.title}</h3>
                  <span className="rounded bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                    {q.category}
                  </span>
                </div>
                <p className="mt-2 text-xs font-medium leading-relaxed">{q.question}</p>
                <div className="mt-3 border-t pt-2">
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Key concepts:
                  </span>
                  <ul className="mt-1 list-inside list-disc space-y-1 text-xs text-muted-foreground">
                    {q.keyPoints.map((pt, i) => (
                      <li key={i}>{pt}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

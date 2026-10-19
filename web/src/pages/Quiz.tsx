/**
 * Quiz page — T1/T2/T3/T4
 *
 * When mounted WITHOUT a `load` prop (the T3 path):
 *   - Shows a setup form (topic chips, file upload, question type, count, marks)
 *   - After setup, POSTs to /quizzes and shows the quiz
 *
 * When mounted WITH a `load` prop (the prep pack path — T3 requirement: unchanged):
 *   - Skips the form and loads the quiz directly
 *
 * T2: Renders BlankItem as a text input with normalize grading.
 * T4: Above the setup form, shows "My progress" with per-topic attempt cards and charts.
 */

import { useEffect, useState } from 'react'
import { FilePick } from '@/components/FilePick'
import { LineChart } from '@/components/LineChart'
import { Button } from '@/components/ui/button'
import { getQuiz, getQuizAttempts, saveAnswers, uploadFile } from '@/api/client'
import type { BlankItem, MCQItem, NumericalItem, Quiz, QuizAttemptsResponse } from '@/api/types'

const demo = !import.meta.env.VITE_API_URL
const wrap = 'mx-auto max-w-3xl px-4 py-6 sm:py-8'

const TOPIC_CHIPS = [
  'Thermodynamics',
  'Reaction engineering',
  'Heat transfer',
  'Mass transfer',
  'Momentum transfer',
  'Process control',
  'Particle technology',
]

// ── Normalize function for blank grading ──────────────────────────────────────

function normalize(s: string): string {
  return s.replace(/\s+/g, ' ').trim().toLowerCase()
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MCQQuestion({
  item,
  index,
  onAnswer,
  answered,
}: {
  item: MCQItem
  index: number
  onAnswer: (idx: number, correct: boolean) => void
  answered: { selected: number; correct: boolean } | null
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="font-medium">
        {index + 1}. {item.stem}
      </p>
      <ul className="mt-3 space-y-2">
        {item.options.map((opt, i) => {
          const isCorrect = i === item.correct_index
          const isSelected = answered?.selected === i
          let cls = 'rounded-lg border p-3 text-sm cursor-pointer transition-colors'
          if (answered) {
            if (isCorrect) cls += ' border-green-500 bg-green-50 text-green-900'
            else if (isSelected) cls += ' border-red-400 bg-red-50 text-red-900'
            else cls += ' opacity-60'
          } else {
            cls += ' hover:bg-muted'
          }
          return (
            <li
              key={i}
              className={cls}
              onClick={() => !answered && onAnswer(i, isCorrect)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && !answered && onAnswer(i, isCorrect)}
            >
              {String.fromCharCode(65 + i)}. {opt}
            </li>
          )
        })}
      </ul>
      {answered && (
        <div className="mt-3 rounded-lg bg-muted p-3 text-sm">
          <p className="font-medium">{answered.correct ? '✓ Correct' : '✗ Incorrect'}</p>
          <p className="mt-1 text-muted-foreground">{item.explanation}</p>
        </div>
      )}
    </div>
  )
}

function BlankQuestion({
  item,
  index,
  onAnswer,
  answered,
}: {
  item: BlankItem
  index: number
  onAnswer: (input: string, correct: boolean) => void
  answered: { input: string; correct: boolean } | null
}) {
  const [value, setValue] = useState('')

  function submit() {
    if (!value.trim() || answered) return
    const correct = item.answers.map(normalize).includes(normalize(value))
    onAnswer(value, correct)
  }

  const parts = item.stem.split('____')

  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="font-medium">
        {index + 1}.{' '}
        <span>
          {parts[0]}
          <span className="inline-block min-w-[80px] border-b-2 border-primary px-2 font-mono">
            {answered ? answered.input : value || '_'}
          </span>
          {parts[1]}
        </span>
      </p>
      {!answered ? (
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            placeholder="Your answer"
            className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm"
          />
          <Button onClick={submit} disabled={!value.trim()}>
            Check
          </Button>
        </div>
      ) : (
        <div className="mt-3 rounded-lg bg-muted p-3 text-sm">
          <p className="font-medium">{answered.correct ? '✓ Correct' : '✗ Incorrect'}</p>
          <p className="mt-1 text-muted-foreground">
            Correct answer{item.answers.length > 1 ? 's' : ''}: {item.answers.join(', ')}
          </p>
          <p className="mt-1 text-muted-foreground">{item.explanation}</p>
        </div>
      )}
    </div>
  )
}

function NumericalQuestion({
  item,
  index,
}: {
  item: NumericalItem
  index: number
}) {
  return (
    <div className="rounded-lg border bg-card p-4 opacity-80">
      <p className="font-medium">
        {index + 1}. {item.stem}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        [Numerical — computed in your browser sandbox]
      </p>
    </div>
  )
}

// ── T4: Progress section ──────────────────────────────────────────────────────

const dtShort = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' })

function ProgressSection() {
  const [attempts, setAttempts] = useState<QuizAttemptsResponse | null>(null)
  useEffect(() => {
    if (demo) return
    getQuizAttempts().then(setAttempts).catch(() => {})
  }, [])

  if (demo || !attempts || !attempts.topics.length) return null

  return (
    <section className="mb-6 rounded-lg border bg-card p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        My progress
      </h2>
      <div className="mt-3 space-y-4">
        {attempts.topics.map((t) => {
          const pcts = t.attempts.map((a) =>
            a.total > 0 ? (a.score / a.total) * 100 : 0,
          )
          const lastPct = pcts.at(-1) ?? 0
          const prevMean =
            pcts.length > 1
              ? pcts.slice(0, -1).reduce((s, v) => s + v, 0) / (pcts.length - 1)
              : null
          const trend =
            prevMean === null
              ? null
              : lastPct - prevMean > 5
                ? 'improving'
                : lastPct - prevMean < -5
                  ? 'dropping'
                  : 'steady'

          return (
            <div key={t.topic} className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{t.topic}</h3>
                {trend && (
                  <span
                    className={`text-xs font-medium ${trend === 'improving' ? 'text-green-600' : trend === 'dropping' ? 'text-red-500' : 'text-muted-foreground'}`}
                  >
                    {trend === 'improving' ? '↑' : trend === 'dropping' ? '↓' : '→'} {trend}
                  </span>
                )}
              </div>
              <ul className="space-y-1 text-xs text-muted-foreground">
                {t.attempts.map((a, i) => {
                  const marks = Math.round(a.score * a.marks_per_q)
                  const totalMarks = Math.round(a.total * a.marks_per_q)
                  const pct = a.total > 0 ? Math.round((a.score / a.total) * 100) : 0
                  const date = a.created_at ? dtShort.format(new Date(a.created_at)) : ''
                  return (
                    <li key={i}>
                      {marks} / {totalMarks} marks ({pct} %) · {date}
                    </li>
                  )
                })}
              </ul>
              {pcts.length >= 2 && (
                <LineChart
                  title=""
                  lines={[{ label: t.topic, values: pcts }]}
                  xLabel="Attempt"
                  yLabel="%"
                />
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ── Setup form (T3) ───────────────────────────────────────────────────────────

type SetupFormProps = {
  onStart: (opts: {
    topic: string
    n_items: number
    kinds: 'mcq' | 'blank' | 'mixed'
    marks_per_q: 1 | 2 | 4
    upload_id?: string
  }) => void
}

function SetupForm({ onStart }: SetupFormProps) {
  const [topic, setTopic] = useState('')
  const [nItems, setNItems] = useState(5)
  const [kinds, setKinds] = useState<'mcq' | 'blank' | 'mixed'>('mcq')
  const [marksPerQ, setMarksPerQ] = useState<1 | 2 | 4>(1)
  const [uploadId, setUploadId] = useState<string | undefined>()
  const [fileName, setFileName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [topicError, setTopicError] = useState(false)

  const totalMarks = nItems * marksPerQ
  const suggestedMin = nItems * (kinds === 'mcq' ? 2 : 3)

  async function handleFile(f: File) {
    setUploading(true)
    setUploadError('')
    setFileName(`Uploading ${f.name}…`)
    try {
      const { upload_id } = await uploadFile(f, 'notes')
      setUploadId(upload_id)
      setFileName(demo ? `Demo — ${f.name} not stored` : f.name)
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
      setFileName('')
    } finally {
      setUploading(false)
    }
  }

  function submit() {
    if (!topic.trim()) {
      setTopicError(true)
      return
    }
    onStart({ topic: topic.trim(), n_items: nItems, kinds, marks_per_q: marksPerQ, upload_id: uploadId })
  }

  return (
    <div className="rounded-lg border bg-card p-5 sm:p-6">
      <h2 className="text-lg font-semibold">Set up your quiz</h2>

      {/* Topic */}
      <div className="mt-4">
        <label htmlFor="quiz-topic" className="block text-sm font-medium">
          Topic <span className="text-destructive">*</span>
        </label>
        <input
          id="quiz-topic"
          type="text"
          maxLength={80}
          value={topic}
          onChange={(e) => { setTopic(e.target.value); setTopicError(false) }}
          placeholder="e.g. Reactor design"
          className={`mt-2 w-full rounded-lg border px-3 py-2 text-sm ${topicError ? 'border-destructive' : 'border-input'} bg-background`}
        />
        {topicError && <p className="mt-1 text-xs text-destructive">Topic is required.</p>}
        <div className="mt-2 flex flex-wrap gap-2">
          {TOPIC_CHIPS.map((chip) => (
            <button
              key={chip}
              type="button"
              onClick={() => { setTopic(chip); setTopicError(false) }}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${topic === chip ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-primary/10'}`}
            >
              {chip}
            </button>
          ))}
        </div>
      </div>

      {/* File upload */}
      <div className="mt-4">
        <FilePick
          label="Add material (optional)"
          disabled={uploading}
          onFile={(f) => void handleFile(f)}
          onError={(m) => { setUploadError(m); setFileName('') }}
        />
        {fileName && <p className="mt-1 text-xs text-muted-foreground">{fileName}</p>}
        {uploadError && <p className="mt-1 text-xs text-destructive">{uploadError}</p>}
      </div>

      {/* Question type */}
      <div className="mt-4">
        <label className="block text-sm font-medium">Question type</label>
        <div className="mt-2 flex gap-2">
          {(['mcq', 'blank', 'mixed'] as const).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKinds(k)}
              className={`rounded-full px-3 py-1 text-xs ${kinds === k ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-primary/10'}`}
            >
              {k === 'mcq' ? 'MCQ' : k === 'blank' ? 'Fill in the blanks' : 'Mixed'}
            </button>
          ))}
        </div>
      </div>

      {/* Number of questions */}
      <div className="mt-4">
        <label className="block text-sm font-medium">Number of questions</label>
        <div className="mt-2 flex gap-2">
          {([5, 10, 15, 20] as const).map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setNItems(n)}
              className={`rounded-full px-3 py-1 text-xs ${nItems === n ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-primary/10'}`}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Marks per question */}
      <div className="mt-4">
        <label className="block text-sm font-medium">Marks per question</label>
        <div className="mt-2 flex gap-2">
          {([1, 2, 4] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMarksPerQ(m)}
              className={`rounded-full px-3 py-1 text-xs ${marksPerQ === m ? 'bg-primary text-primary-foreground' : 'bg-muted hover:bg-primary/10'}`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Live summary */}
      <p className="mt-4 text-sm text-muted-foreground" aria-live="polite">
        Total: <strong>{totalMarks} marks</strong> · Suggested time:{' '}
        <strong>{suggestedMin} min</strong> (keep time yourself)
      </p>

      <Button className="mt-5 w-full sm:w-auto" onClick={submit}>
        Make quiz
      </Button>
    </div>
  )
}

// ── Main Quiz component ───────────────────────────────────────────────────────

export type QuizPageProps = {
  /** Prep-pack path: load with these opts, skip setup form. */
  load?: {
    topic: string
    n_items?: number
    kinds?: 'mcq' | 'blank' | 'mixed'
    marks_per_q?: 1 | 2 | 4
  }
}

type QuizAnswer =
  | { type: 'mcq'; selected: number; correct: boolean }
  | { type: 'blank'; input: string; correct: boolean }
  | { type: 'numerical'; skipped: true }

export default function Quiz({ load }: QuizPageProps) {
  const [quiz, setQuiz] = useState<Quiz | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState<Record<number, QuizAnswer>>({})
  const [submitted, setSubmitted] = useState(false)

  // Auto-load when `load` prop is provided (prep-pack mode)
  useEffect(() => {
    if (!load) return
    let ignore = false
    void getQuiz(load as Parameters<typeof getQuiz>[0])
      .then((q) => {
        if (!ignore) setQuiz(q)
      })
      .catch((e) => {
        if (!ignore) setError(e instanceof Error ? e.message : 'Failed to load quiz')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleStart(opts: Parameters<typeof getQuiz>[0]) {
    setLoading(true)
    setError('')
    setAnswers({})
    setSubmitted(false)
    try {
      const q = await getQuiz(opts)
      setQuiz(q)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate quiz')
    } finally {
      setLoading(false)
    }
  }

  function answerItem(index: number, answer: QuizAnswer) {
    setAnswers((prev) => ({ ...prev, [index]: answer }))
  }

  async function submitQuiz() {
    if (!quiz) return
    const correct: (boolean | null)[] = quiz.items.map((_, i) => {
      const a = answers[i]
      if (!a) return null
      if (a.type === 'numerical') return null
      return a.correct
    })
    const score = correct.filter(Boolean).length
    const answerList: (number | string | null)[] = quiz.items.map((_, i) => {
      const a = answers[i]
      if (!a) return null
      if (a.type === 'mcq') return a.selected
      if (a.type === 'blank') return a.input
      return null
    })
    setSubmitted(true)
    if (quiz.id) {
      await saveAnswers(quiz.id, answerList, score, correct).catch(() => {})
    }
  }

  // ── Result screen ──────────────────────────────────────────────────────────
  if (submitted && quiz) {
    const marksPerQ = quiz.marks_per_q ?? 1
    const total_marks = quiz.total_marks ?? quiz.items.length * marksPerQ
    const correct = quiz.items.map((_, i) => {
      const a = answers[i]
      if (!a || a.type === 'numerical') return null
      return a.correct
    })
    const scored = correct.filter(Boolean).length
    const marks = scored * marksPerQ
    const pct = total_marks > 0 ? Math.round((marks / total_marks) * 100) : 0

    return (
      <main className={wrap}>
        <div className="rounded-lg border bg-card p-6 text-center">
          <h1 className="text-2xl font-semibold">Quiz complete!</h1>
          <p className="mt-3 text-4xl font-bold text-primary">
            {marks} / {total_marks} marks
          </p>
          <p className="mt-1 text-muted-foreground">({pct}%)</p>
          <Button className="mt-6" onClick={() => { setQuiz(null); setAnswers({}); setSubmitted(false) }}>
            Take another quiz
          </Button>
        </div>
      </main>
    )
  }

  // ── Quiz in progress ───────────────────────────────────────────────────────
  if (quiz) {
    const allAnswered = quiz.items.every((item, i) => item.type === 'numerical' || i in answers)

    return (
      <main className={wrap}>
        <h1 className="text-2xl font-semibold tracking-tight">{quiz.title}</h1>
        {quiz.suggested_minutes && (
          <p className="mt-1 text-sm text-muted-foreground">
            Suggested time: {quiz.suggested_minutes} min (keep time yourself)
          </p>
        )}
        <div className="mt-4 space-y-4">
          {quiz.items.map((item, i) => {
            if (item.type === 'mcq') {
              const ans = answers[i] as { type: 'mcq'; selected: number; correct: boolean } | undefined
              return (
                <MCQQuestion
                  key={i}
                  item={item}
                  index={i}
                  answered={ans ? { selected: ans.selected, correct: ans.correct } : null}
                  onAnswer={(selected, correct) => answerItem(i, { type: 'mcq', selected, correct })}
                />
              )
            }
            if (item.type === 'blank') {
              const ans = answers[i] as { type: 'blank'; input: string; correct: boolean } | undefined
              return (
                <BlankQuestion
                  key={i}
                  item={item}
                  index={i}
                  answered={ans ? { input: ans.input, correct: ans.correct } : null}
                  onAnswer={(input, correct) => answerItem(i, { type: 'blank', input, correct })}
                />
              )
            }
            return <NumericalQuestion key={i} item={item as NumericalItem} index={i} />
          })}
        </div>
        {allAnswered && (
          <Button className="mt-6 w-full sm:w-auto" onClick={() => void submitQuiz()}>
            Submit quiz
          </Button>
        )}
      </main>
    )
  }

  // ── Setup form (T3) or loading state ──────────────────────────────────────
  if (loading) {
    return (
      <main className={wrap}>
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 rounded-lg bg-muted" />
          <div className="h-48 rounded-lg bg-muted" />
        </div>
      </main>
    )
  }

  if (error) {
    return (
      <main className={wrap}>
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
        <Button className="mt-2" onClick={() => setError('')}>
          Try again
        </Button>
      </main>
    )
  }

  // Only show setup form when no `load` prop (T3 requirement)
  if (load) return null

  return (
    <main className={wrap}>
      {/* T4: My progress (signed-in only) */}
      <ProgressSection />

      <SetupForm onStart={(opts) => void handleStart(opts)} />
    </main>
  )
}

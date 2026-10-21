import { useEffect, useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { FilePick } from '@/components/FilePick'
import { LineChart } from '@/components/LineChart'
import { getQuiz, getQuizAttempts, savePractice, uploadFile } from '@/api/client'
import { friendly } from '@/lib/errors'
import type { QuizAttempts } from '@/api/types'

export type BankQ = {
  id: string
  section: string
  topic: string
  q: string
  options: string[]
  answer: number
  explain: string
}

export type CompanySummary = {
  id: string
  company: string
  sector: string
  roles: string[]
}

export type CompanyDetail = {
  id: string
  company: string
  roles: string[]
  note: string
  oa: {
    sections: { name: string; questions: number; minutes: number }[]
    draw: number
    marks_per_q: number
    bank: BankQ[]
  }
  interview: {
    rounds: string[]
    about: string
    looks_for: string[]
    selection: string[]
    technical: { q: string; a: string }[]
    hr: { q: string; how: string }[]
    present: string[]
    tips: string[]
  }
  sources: string[]
}

const dtShort = new Intl.DateTimeFormat('en', { day: 'numeric', month: 'short' })

function shuffle<T>(array: T[]): T[] {
  const arr = [...array]
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[arr[i], arr[j]] = [arr[j], arr[i]]
  }
  return arr
}

// ── Exam Component ─────────────────────────────────────────────────────────────
export function Exam({
  title,
  questions,
  saveTopic,
  strengthsKey,
  onDone,
}: {
  title: string
  questions: BankQ[]
  saveTopic: string
  strengthsKey?: string // company id: OA attempts feed that company's topic strengths
  onDone: () => void
}) {
  const [currentIdx, setCurrentIdx] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [submitted, setSubmitted] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)

  if (!questions || questions.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 text-center">
        <p className="text-muted-foreground">No questions available for this exam.</p>
        <Button className="mt-4" onClick={onDone}>
          Back
        </Button>
      </div>
    )
  }

  const currentQ = questions[currentIdx]

  const handleSubmit = async () => {
    let correct = 0
    for (let i = 0; i < questions.length; i++) {
      if (answers[i] === questions[i].answer) {
        correct++
      }
    }

    setSubmitted(true)

    // Save practice result
    try {
      await savePractice(saveTopic, correct, questions.length, 1)
    } catch {
      setSaveStatus('Not saved (sign in to track progress)')
    }

    // Update topic strengths in browser storage (keyed by company id, the same key the company screen reads)
    if (strengthsKey) try {
      const raw = localStorage.getItem('studyforge.companyoa.v1')
      const storage = raw ? JSON.parse(raw) : {}
      const key = strengthsKey.toLowerCase().replace(/[^a-z0-9]/g, '')

      if (!storage[key]) storage[key] = {}

      for (let i = 0; i < questions.length; i++) {
        const top = questions[i].topic
        if (!storage[key][top]) {
          storage[key][top] = { asked: 0, correct: 0 }
        }
        storage[key][top].asked += 1
        if (answers[i] === questions[i].answer) {
          storage[key][top].correct += 1
        }
      }
      localStorage.setItem('studyforge.companyoa.v1', JSON.stringify(storage))
    } catch {
      // ignore storage errors
    }
  }

  // ── Results screen ───────────────────────────────────────────────────────────
  if (submitted) {
    let correct = 0
    const topicStats: Record<string, { asked: number; correct: number }> = {}

    for (let i = 0; i < questions.length; i++) {
      const q = questions[i]
      const isCorrect = answers[i] === q.answer
      if (isCorrect) correct++

      if (!topicStats[q.topic]) {
        topicStats[q.topic] = { asked: 0, correct: 0 }
      }
      topicStats[q.topic].asked += 1
      if (isCorrect) topicStats[q.topic].correct += 1
    }

    const total = questions.length
    const score = correct * 1
    const totalMarks = total * 1
    const pct = total > 0 ? Math.round((correct / total) * 100) : 0

    const weakTopics = Object.entries(topicStats)
      .filter(([, s]) => s.asked > 0 && s.correct / s.asked < 0.6)
      .map(([top]) => top)

    return (
      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6 shadow-sm">
          <h2 className="text-xl font-bold tracking-tight">{title}</h2>
          <div className="mt-4 rounded-md bg-muted/50 p-4">
            <p className="text-2xl font-extrabold text-primary">
              Score: {score} / {totalMarks} marks ({pct} %)
            </p>
            {saveStatus && <p className="mt-1 text-xs text-muted-foreground">{saveStatus}</p>}
          </div>

          <div className="mt-6 space-y-2">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              By topic this attempt
            </h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {Object.entries(topicStats).map(([top, s]) => {
                const topicPct = Math.round((s.correct / s.asked) * 100)
                return (
                  <div key={top} className="flex justify-between rounded border p-2 text-xs">
                    <span className="font-medium">{top}</span>
                    <span className="text-muted-foreground">
                      {s.correct} / {s.asked} ({topicPct} %)
                    </span>
                  </div>
                )
              })}
            </div>
            {weakTopics.length > 0 && (
              <p className="mt-2 text-xs font-semibold text-destructive">
                Work on: {weakTopics.join(', ')}
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => {
                setAnswers({})
                setCurrentIdx(0)
                setSubmitted(false)
                setSaveStatus(null)
              }}
            >
              Try another set
            </Button>
            <Button onClick={onDone}>Choose another company</Button>
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="text-lg font-bold">Review Questions</h3>
          {questions.map((q, idx) => {
            const userChoice = answers[idx]
            const isCorrect = userChoice === q.answer
            return (
              <div
                key={q.id || idx}
                className={`rounded-lg border p-4 transition-colors ${
                  isCorrect ? 'border-green-200 bg-green-50/30' : 'border-red-200 bg-red-50/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Question {idx + 1} · {q.topic}
                  </span>
                  <span
                    className={`text-xs font-bold ${
                      isCorrect ? 'text-green-700' : 'text-destructive'
                    }`}
                  >
                    {isCorrect ? 'Correct' : 'Incorrect'}
                  </span>
                </div>
                <p className="mt-2 text-sm font-medium leading-relaxed">{q.q}</p>
                <div className="mt-3 space-y-1 text-xs">
                  <p>
                    <span className="font-semibold text-muted-foreground">Your choice: </span>
                    <span className={isCorrect ? 'text-green-700 font-medium' : 'text-destructive font-medium'}>
                      {userChoice !== undefined ? q.options[userChoice] : 'Not answered'}
                    </span>
                  </p>
                  {!isCorrect && (
                    <p>
                      <span className="font-semibold text-muted-foreground">Correct option: </span>
                      <span className="font-medium text-green-700">{q.options[q.answer]}</span>
                    </p>
                  )}
                  {q.explain && (
                    <div className="mt-2 rounded bg-muted/60 p-2.5 text-xs text-muted-foreground">
                      <span className="font-semibold text-foreground">Explanation: </span>
                      {q.explain}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  // ── Active question view (NEVER reveals answers before Submit) ───────────────
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between border-b pb-4">
        <div>
          <h2 className="text-base font-bold">{title}</h2>
          <p className="text-xs text-muted-foreground">
            Question {currentIdx + 1} of {questions.length} · {currentQ.topic}
          </p>
        </div>
        <Button variant="ghost" size="sm" onClick={onDone}>
          Exit
        </Button>
      </div>

      <div className="py-6">
        <p className="text-sm font-medium leading-relaxed sm:text-base">{currentQ.q}</p>

        <div className="mt-6 space-y-2.5">
          {currentQ.options.map((opt, oIdx) => {
            const isChecked = answers[currentIdx] === oIdx
            return (
              <label
                key={oIdx}
                className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3.5 text-sm transition-colors ${
                  isChecked
                    ? 'border-primary bg-primary/5 text-foreground font-medium'
                    : 'border-border bg-card hover:bg-accent/40'
                }`}
              >
                <input
                  type="radio"
                  name={`question-${currentIdx}`}
                  className="mt-0.5"
                  checked={isChecked}
                  onChange={() => setAnswers({ ...answers, [currentIdx]: oIdx })}
                />
                <span className="flex-1">{opt}</span>
              </label>
            )
          })}
        </div>
      </div>

      <div className="flex items-center justify-between border-t pt-4">
        <Button
          variant="outline"
          disabled={currentIdx === 0}
          onClick={() => setCurrentIdx(currentIdx - 1)}
        >
          Previous
        </Button>

        {currentIdx < questions.length - 1 ? (
          <Button onClick={() => setCurrentIdx(currentIdx + 1)}>Next</Button>
        ) : (
          <Button onClick={handleSubmit}>Submit</Button>
        )}
      </div>
    </div>
  )
}

// ── CompanyOA Component ────────────────────────────────────────────────────────
export default function CompanyOA({ initial }: { initial?: string }) {
  const [companies, setCompanies] = useState<CompanySummary[]>([])
  const [search, setSearch] = useState('')
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(initial || null)
  const [prevInitial, setPrevInitial] = useState(initial)
  if (initial !== prevInitial) {
    setPrevInitial(initial)
    if (initial) {
      setSelectedCompanyId(initial)
    }
  }
  const [companyData, setCompanyData] = useState<CompanyDetail | null>(null)
  const loadingCompany = Boolean(selectedCompanyId && !companyData)

  // Exam view state
  const [examActive, setExamActive] = useState(false)
  const [examQuestions, setExamQuestions] = useState<BankQ[]>([])
  const [examTitle, setExamTitle] = useState('')
  const [examSaveTopic, setExamSaveTopic] = useState('')

  // Progress state
  const [attempts, setAttempts] = useState<QuizAttempts | null>(null)

  // Topic strengths derived from browser storage
  const topicStrengths = useMemo(() => {
    if (!companyData) return []
    try {
      const raw = localStorage.getItem('studyforge.companyoa.v1')
      if (!raw) return []
      const parsed = JSON.parse(raw)
      const key = companyData.id.toLowerCase().replace(/[^a-z0-9]/g, '')
      const compTopics = parsed[key] || {}
      const items = Object.entries(compTopics).map(([topic, s]: [string, any]) => {
        const asked = s.asked || 0
        const correct = s.correct || 0
        const pct = asked > 0 ? Math.round((correct / asked) * 100) : 0
        return { topic, asked, correct, pct }
      })
      items.sort((a, b) => a.pct - b.pct)
      return items
    } catch {
      return []
    }
  }, [companyData])

  // Own-material state
  const [ownUploadId, setOwnUploadId] = useState<string | null>(null)
  const [ownFileName, setOwnFileName] = useState<string | null>(null)
  const [ownUploading, setOwnUploading] = useState(false)
  const [ownMakingQuiz, setOwnMakingQuiz] = useState(false)
  const [ownError, setOwnError] = useState<string | null>(null)

  const isDemo = !import.meta.env.VITE_API_URL

  // Load index.json on mount (ONLY the 15 summaries, never the full files)
  useEffect(() => {
    import('../data/companies/index.json').then((mod) => {
      setCompanies((mod.default || mod) as CompanySummary[])
    })
  }, [])

  // Lazy load company file when selected
  useEffect(() => {
    if (!selectedCompanyId) return

    const files = import.meta.glob('../data/companies/*.json')
    const key = `../data/companies/${selectedCompanyId}.json`
    const loader = files[key]

    if (loader) {
      loader()
        .then((mod: unknown) => {
          const data = (mod as { default: CompanyDetail }).default || (mod as CompanyDetail)
          setCompanyData(data)
        })
        .catch(() => {})
    }
  }, [selectedCompanyId])

  // Fetch attempts whenever company data changes
  useEffect(() => {
    if (!companyData) return

    getQuizAttempts()
      .then(setAttempts)
      .catch(() => setAttempts(null))
  }, [companyData])

  // Start standard practice test
  const handleStartPractice = () => {
    if (!companyData) return
    const drawn = shuffle(companyData.oa.bank).slice(0, companyData.oa.draw)
    setExamTitle(`${companyData.company} OA Practice`)
    setExamSaveTopic(`OA: ${companyData.company}`)
    setExamQuestions(drawn)
    setExamActive(true)
  }

  // Handle own-material file upload
  const handleFilePicked = async (file: File) => {
    setOwnUploading(true)
    setOwnError(null)
    setOwnFileName(file.name)
    try {
      const res = await uploadFile(file, 'notes')
      setOwnUploadId(res.upload_id)
    } catch (e) {
      setOwnError(friendly(e))
      setOwnFileName(null)
      setOwnUploadId(null)
    } finally {
      setOwnUploading(false)
    }
  }

  // Handle "Make my test" from own material
  const handleMakeOwnTest = async () => {
    if (!ownUploadId || !companyData) return
    setOwnMakingQuiz(true)
    setOwnError(null)

    try {
      const res = await getQuiz({
        topic: `OA: ${companyData.company}`,
        n_items: 15,
        kinds: 'mcq',
        marks_per_q: 1,
        upload_id: ownUploadId,
      })

      const mcqItems = (res.items || []).filter((item: any) => item.type === 'mcq')
      if (mcqItems.length < 3) {
        setOwnError("Couldn't make enough questions from this material. Try a clearer file.")
        return
      }

      const converted: BankQ[] = mcqItems.map((item: any, i: number) => ({
        id: String(i),
        section: 'Your material',
        topic: item.topic || 'General',
        q: item.stem,
        options: item.options,
        answer: item.correct_index,
        explain: item.explanation || '',
      }))

      setExamTitle(`${companyData.company} practice (your material)`)
      setExamSaveTopic(`OA: ${companyData.company}`)
      setExamQuestions(converted)
      setExamActive(true)
    } catch (e) {
      setOwnError(friendly(e))
    } finally {
      setOwnMakingQuiz(false)
    }
  }

  // If exam active, show exam screen
  if (examActive) {
    return (
      <Exam
        title={examTitle}
        questions={examQuestions}
        saveTopic={examSaveTopic}
        strengthsKey={companyData?.id}
        onDone={() => {
          setExamActive(false)
          setSelectedCompanyId(null)
          setCompanyData(null)
        }}
      />
    )
  }

  // If company selected, show company detail screen
  if (selectedCompanyId && companyData) {
    const totalMinutes = companyData.oa.sections.reduce((acc, s) => acc + s.minutes, 0)
    const topicTarget = `OA: ${companyData.company}`
    const matchingTopic = attempts?.topics?.find((t) => t.topic === topicTarget)
    const companyAttempts = matchingTopic?.attempts || []

    const pcts = companyAttempts.map((a) => (a.total > 0 ? (a.score / a.total) * 100 : 0))
    const lastPct = pcts.at(-1) ?? 0
    const prevMean =
      pcts.length > 1 ? pcts.slice(0, -1).reduce((s, v) => s + v, 0) / (pcts.length - 1) : null
    const trend =
      prevMean === null
        ? null
        : lastPct - prevMean > 5
        ? 'improving'
        : lastPct - prevMean < -5
        ? 'dropping'
        : 'steady'

    const suggestedFocus = topicStrengths
      .filter((t) => t.asked >= 3)
      .slice(0, 2)
      .map((t) => t.topic)

    return (
      <div className="space-y-6">
        <div>
          <button
            type="button"
            className="text-xs font-medium text-primary hover:underline"
            onClick={() => {
              setSelectedCompanyId(null)
              setCompanyData(null)
            }}
          >
            ← Back to companies
          </button>
          <h1 className="mt-2 text-2xl font-bold tracking-tight">{companyData.company}</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Roles: {companyData.roles.join(', ')}
          </p>
          <p className="mt-1 text-xs text-muted-foreground/80 italic">{companyData.note}</p>
        </div>

        {/* ── Per-company progress section ────────────────────────────────────── */}
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-semibold tracking-tight">
            Your progress at {companyData.company}
          </h2>

          <div className="mt-3 space-y-4">
            {/* Score graph / history */}
            <div>
              {companyAttempts.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  {isDemo || !attempts ? 'Sign in to track progress' : 'No practice attempts yet.'}
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Recent attempts
                    </span>
                    {trend && (
                      <span
                        className={`text-xs font-medium ${
                          trend === 'improving'
                            ? 'text-green-600'
                            : trend === 'dropping'
                            ? 'text-red-500'
                            : 'text-muted-foreground'
                        }`}
                      >
                        {trend === 'improving' ? '↑' : trend === 'dropping' ? '↓' : '→'} {trend}
                      </span>
                    )}
                  </div>
                  <ul className="space-y-1 text-xs text-muted-foreground">
                    {companyAttempts.map((a, i) => {
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
                      title={`${companyData.company}: score per attempt`}
                      lines={[{ name: 'Score %', x: pcts.map((_, i) => i + 1), y: pcts, color: 'var(--primary)' }]}
                      xLabel="attempt"
                      yLabel="%"
                    />
                  )}
                </div>
              )}
            </div>

            {/* Topic strengths */}
            {topicStrengths.length > 0 && (
              <div className="border-t pt-3">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Topic strengths
                </h3>
                <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
                  {topicStrengths.map((t) => (
                    <div key={t.topic} className="flex justify-between text-xs">
                      <span>{t.topic}</span>
                      <span className="text-muted-foreground">
                        {t.correct} / {t.asked} ({t.pct} %)
                      </span>
                    </div>
                  ))}
                </div>
                {suggestedFocus.length > 0 && (
                  <p className="mt-2 text-xs font-semibold text-primary">
                    Suggested focus: {suggestedFocus.join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>
        </section>

        {/* ── OA Sections Table ──────────────────────────────────────────────── */}
        <section className="space-y-3">
          <h2 className="text-sm font-semibold tracking-tight">Assessment structure</h2>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-xs">
              <thead className="border-b bg-muted/50 font-medium text-muted-foreground">
                <tr>
                  <th className="p-2.5">Section</th>
                  <th className="p-2.5">Questions</th>
                  <th className="p-2.5">Duration</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {companyData.oa.sections.map((s, idx) => (
                  <tr key={idx} className="hover:bg-muted/20">
                    <td className="p-2.5 font-medium">{s.name}</td>
                    <td className="p-2.5 text-muted-foreground">{s.questions}</td>
                    <td className="p-2.5 text-muted-foreground">{s.minutes} min</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">This practice draws {companyData.oa.draw} questions from the bank.</p>
          <p className="text-xs text-muted-foreground">
            Suggested time: {totalMinutes} min (keep time yourself)
          </p>
        </section>

        <Button size="lg" className="w-full sm:w-auto" onClick={handleStartPractice}>
          Start practice
        </Button>

        {/* ── Own-material box (§3a) ─────────────────────────────────────────── */}
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-semibold tracking-tight">Practise from your own material</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Got a newer syllabus or notes? Upload a PDF or photo and we'll make a 15-question
            practice test from it.
          </p>

          <div className="mt-3 space-y-3">
            {isDemo ? (
              <p className="text-xs text-muted-foreground">
                Sign in to practise from your own material.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <FilePick
                    label="Upload syllabus / notes"
                    disabled={ownUploading || ownMakingQuiz}
                    onFile={handleFilePicked}
                    onError={(m) => setOwnError(m)}
                  />
                  {ownUploading && <span className="text-xs text-muted-foreground">uploading…</span>}
                  {ownFileName && !ownUploading && (
                    <span className="text-xs font-medium text-primary">{ownFileName}</span>
                  )}
                </div>

                <Button
                  variant="secondary"
                  disabled={!ownUploadId || ownUploading || ownMakingQuiz}
                  onClick={handleMakeOwnTest}
                >
                  {ownMakingQuiz ? 'Making your test…' : 'Make my test'}
                </Button>

                {ownError && <p className="text-xs text-destructive">{ownError}</p>}
                <p className="text-[11px] text-muted-foreground/75">
                  Uses the AI to read your material.
                </p>
              </>
            )}
          </div>
        </section>
      </div>
    )
  }

  // Company list view
  const filtered = companies.filter((c) =>
    c.company.toLowerCase().includes(search.toLowerCase().trim()),
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Company OA Practice</h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Simulated online assessments for top chemical, energy, and process engineering companies.
        </p>
      </div>

      <div>
        <input
          type="text"
          placeholder="Search company..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        />
      </div>

      {loadingCompany ? (
        <div className="py-8 text-center text-xs text-muted-foreground">Loading company...</div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setSelectedCompanyId(c.id)}
              className="flex flex-col items-start rounded-lg border bg-card p-4 text-left transition-all hover:border-primary/50 hover:shadow-sm"
            >
              <h2 className="text-sm font-semibold">{c.company}</h2>
              <span className="mt-1 inline-block rounded bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                {c.sector}
              </span>
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="col-span-full py-8 text-center text-xs text-muted-foreground">
              No matching companies found.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { FilePick } from '@/components/FilePick'
import { Exam, type BankQ, type CompanyDetail, type CompanySummary } from '@/components/CompanyOA'
import { getQuiz, uploadFile } from '@/api/client'
import { friendly } from '@/lib/errors'

export default function ChemInterview() {
  const [companies, setCompanies] = useState<CompanySummary[]>([])
  const [search, setSearch] = useState('')
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)
  const [companyData, setCompanyData] = useState<CompanyDetail | null>(null)
  const loadingCompany = Boolean(selectedCompanyId && !companyData)

  // Exam view state (for own-material practice)
  const [examActive, setExamActive] = useState(false)
  const [examQuestions, setExamQuestions] = useState<BankQ[]>([])
  const [examTitle, setExamTitle] = useState('')
  const [examSaveTopic, setExamSaveTopic] = useState('')

  // Own-material state
  const [ownUploadId, setOwnUploadId] = useState<string | null>(null)
  const [ownFileName, setOwnFileName] = useState<string | null>(null)
  const [ownUploading, setOwnUploading] = useState(false)
  const [ownMakingQuiz, setOwnMakingQuiz] = useState(false)
  const [ownError, setOwnError] = useState<string | null>(null)

  const isDemo = !import.meta.env.VITE_API_URL

  // Load index.json on mount (ONLY the 15 summaries)
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

  // Handle "Make practice questions" from own material
  const handleMakeOwnQuestions = async () => {
    if (!ownUploadId || !companyData) return
    setOwnMakingQuiz(true)
    setOwnError(null)

    try {
      const res = await getQuiz({
        topic: `Interview: ${companyData.company}`,
        n_items: 10,
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
        topic: item.topic || 'Interview',
        q: item.stem,
        options: item.options,
        answer: item.correct_index,
        explain: item.explanation || '',
      }))

      setExamTitle(`${companyData.company} interview practice`)
      setExamSaveTopic(`Interview: ${companyData.company}`)
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
        onDone={() => setExamActive(false)}
      />
    )
  }

  // If company selected, show interview page
  if (selectedCompanyId && companyData) {
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
          <p className="mt-3 text-sm leading-relaxed">{companyData.interview.about}</p>
        </div>

        {/* ── What company looks for (always shown) ──────────────────────────── */}
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-semibold tracking-tight">
            What {companyData.company} looks for
          </h2>
          <ul className="mt-2 list-inside list-disc space-y-1.5 text-xs text-muted-foreground">
            {companyData.interview.looks_for.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </section>

        {/* ── How they select (always shown) ─────────────────────────────────── */}
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-semibold tracking-tight">How they select</h2>
          <ul className="mt-2 list-inside list-disc space-y-1.5 text-xs text-muted-foreground">
            {companyData.interview.selection.map((pt, i) => (
              <li key={i}>{pt}</li>
            ))}
          </ul>
        </section>

        {/* ── Collapsible sections ────────────────────────────────────────────── */}
        <div className="space-y-3">
          {/* Interview process */}
          <details className="group rounded-lg border bg-card p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-sm select-none">
              Interview process
            </summary>
            <ol className="mt-3 list-inside list-decimal space-y-2 text-xs text-muted-foreground">
              {companyData.interview.rounds.map((round, i) => (
                <li key={i} className="font-medium text-foreground">
                  <span className="text-muted-foreground">{round}</span>
                </li>
              ))}
            </ol>
          </details>

          {/* Technical questions */}
          <details className="group rounded-lg border bg-card p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-sm select-none">
              Technical questions ({companyData.interview.technical.length})
            </summary>
            <div className="mt-3 divide-y">
              {companyData.interview.technical.map((item, i) => (
                <div key={i} className="py-3 first:pt-0 last:pb-0">
                  <p className="text-xs font-semibold text-foreground">Q: {item.q}</p>
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-primary">Model Answer: </span>
                    {item.a}
                  </p>
                </div>
              ))}
            </div>
          </details>

          {/* HR questions */}
          <details className="group rounded-lg border bg-card p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-sm select-none">
              HR questions ({companyData.interview.hr.length})
            </summary>
            <div className="mt-3 divide-y">
              {companyData.interview.hr.map((item, i) => (
                <div key={i} className="py-3 first:pt-0 last:pb-0">
                  <p className="text-xs font-semibold text-foreground">Q: {item.q}</p>
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-primary">How to answer: </span>
                    {item.how}
                  </p>
                </div>
              ))}
            </div>
          </details>

          {/* How to present yourself */}
          <details className="group rounded-lg border bg-card p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-sm select-none">
              How to present yourself
            </summary>
            <ul className="mt-3 list-inside list-disc space-y-1.5 text-xs text-muted-foreground">
              {companyData.interview.present.map((pt, i) => (
                <li key={i}>{pt}</li>
              ))}
            </ul>
          </details>

          {/* Tips */}
          <details className="group rounded-lg border bg-card p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-sm select-none">
              Tips
            </summary>
            <ul className="mt-3 list-inside list-disc space-y-1.5 text-xs text-muted-foreground">
              {companyData.interview.tips.map((pt, i) => (
                <li key={i}>{pt}</li>
              ))}
            </ul>
          </details>
        </div>

        {/* ── Own-material box (§3a) ─────────────────────────────────────────── */}
        <section className="rounded-lg border bg-card p-4 shadow-sm">
          <h2 className="text-sm font-semibold tracking-tight">Prepare from your own material</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Upload the job description, a new syllabus or your notes to practise likely interview topics.
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
                    label="Upload JD / syllabus / notes"
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
                  onClick={handleMakeOwnQuestions}
                >
                  {ownMakingQuiz ? 'Making practice questions…' : 'Make practice questions'}
                </Button>

                {ownError && <p className="text-xs text-destructive">{ownError}</p>}
                <p className="text-[11px] text-muted-foreground/75">
                  Uses the AI to read your material.
                </p>
              </>
            )}
          </div>
        </section>

        {/* ── Direct practice link to OA ──────────────────────────────────────── */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-t pt-4">
          <a
            href={`#oa?company=${companyData.id}`}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            Practice this company's OA
          </a>

          {companyData.sources.length > 0 && (
            <div className="text-[11px] text-muted-foreground">
              Sources:{' '}
              {companyData.sources.map((src, i) => (
                <span key={i}>
                  <a
                    href={src}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline hover:text-foreground"
                  >
                    [{i + 1}]
                  </a>
                  {i < companyData.sources.length - 1 ? ' ' : ''}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // Company list picker
  const filtered = companies.filter((c) =>
    c.company.toLowerCase().includes(search.toLowerCase().trim()),
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Chemical Company Interview Prep</h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Real interview questions, process breakdowns, and tips for leading chemical and energy corporations.
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

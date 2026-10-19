// Solve endpoints of the frozen API contract (master plan §3.5). Types marked "gap" are not specified there.
export type Step =
  | { type: 'run_python'; code: string; timeout_s: 10 }
  | { type: 'need_confirm'; extracted_text: string }
  | {
      type: 'final'
      answer_md: string
      numbers: Record<string, number> // gap
      figures: string[] // gap: image URLs or data: URLs
      diagram_mermaid?: string
      sources: { title: string; url?: string }[] // gap
      confidence: 'high' | 'medium' | 'low' // gap
    }
export type SolveStart = { solve_id: string; step: Step }
export type ResultBody = { stdout: string; result: unknown; figures: string[]; error: string | null; ms: number }

export type UploadRead = { text: string; latex: string; confidence: 'high' | 'medium' | 'low' } // POST /uploads/{id}/read
export type UploadKind = 'question' | 'notes' // gap: contract doesn't say how the server tells these apart; we send multipart field `kind`

// GET /api/v1/dashboard: PROPOSED (E1), not in the frozen contract yet.
export type Task = { id: string; title: string; action: string; due_at_utc: string; source: string; status: 'open' | 'done' }
export type WeakTopic = { topic: string; attempts: number; correct: number }
export type RecentSolve = { id: string; question: string; status: string; created_at: string }
export type Reminder = { id: string; title: string; due_at_utc: string; sent_at: string | null; channel: 'app' | 'push' } // push = phone notification (D1b); Telegram dropped 10 Oct
export type Dashboard = { tasks: Task[]; weak_topics: WeakTopic[]; recent_solves: RecentSolve[]; reminders: Reminder[] }

// ── Quiz types (T1/T2/T3) ─────────────────────────────────────────────────────
export type MCQItem = {
  type: 'mcq'
  topic: string
  stem: string
  options: string[]
  correct_index: number
  misconceptions: Record<string, string>
  explanation: string
  source?: string | null
  tags?: string[]
}

export type NumericalItem = {
  type: 'numerical'
  topic: string
  stem: string
  key_code: string
  unit: string
  tolerance_rel?: number
  worked_solution: string
  source?: string | null
  tags?: string[]
}

export type BlankItem = {
  type: 'blank'
  topic: string
  stem: string
  answers: string[]
  explanation: string
  source?: string | null
  tags?: string[]
}

export type SubjectiveItem = {
  type: 'subjective'
  topic: string
  stem: string
  rubric: string[]
  source?: string | null
  tags?: string[]
}

export type QuizItem = MCQItem | NumericalItem | BlankItem | SubjectiveItem

export type Quiz = {
  id?: string
  title: string
  items: QuizItem[]
  topic?: string
  marks_per_q?: number
  total_marks?: number
  suggested_minutes?: number
}

export type QuizOpts = {
  topic: string
  n_items?: number
  kinds?: 'mcq' | 'blank' | 'mixed'
  marks_per_q?: 1 | 2 | 4
  upload_id?: string
}

// ── T4: Quiz attempts ──────────────────────────────────────────────────────────
export type QuizAttempt = {
  quiz_id: string
  score: number
  total: number
  marks_per_q: number
  created_at: string
}

export type TopicAttempts = {
  topic: string
  attempts: QuizAttempt[]
}

export type QuizAttemptsResponse = { topics: TopicAttempts[] }

// ── T5: Solve history ─────────────────────────────────────────────────────────
// T5: GET /api/v1/solves
export type SolveItem = {
  id: string
  question: string
  status: string
  updated_at: string | null
}
export type SolvesResponse = {
  items: SolveItem[]
  next: string | null
}

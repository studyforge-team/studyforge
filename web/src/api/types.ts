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
export type Reminder = { id: string; title: string; due_at_utc: string; sent_at: string | null; channel: 'app' | 'telegram' }
export type Dashboard = { tasks: Task[]; weak_topics: WeakTopic[]; recent_solves: RecentSolve[]; reminders: Reminder[] }

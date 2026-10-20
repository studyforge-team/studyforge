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

// Quiz schema mirrors api/app/agent/quiz.py (Q1). GET/POST /quizzes is §3.5; `id` is a gap (contract returns no quiz id yet).
type ItemBase = { topic: string; source: string | null; tags: string[]; stem: string }
export type MCQItem = ItemBase & { type: 'mcq'; options: string[]; correct_index: number; misconceptions: Record<string, string>; explanation: string } // keys "0".."3"
export type NumericalItem = ItemBase & { type: 'numerical'; key_code: string; unit: string; tolerance_rel: number; worked_solution: string }
export type SubjectiveItem = ItemBase & { type: 'subjective'; rubric: string[] }
export type BlankItem = ItemBase & { type: 'blank'; answers: string[]; explanation: string } // stem contains ____
export type QuizItem = MCQItem | NumericalItem | SubjectiveItem | BlankItem
export type CheckinResult = { done: boolean; follow_up_at: string | null }
// topic..suggested_minutes: only POST /quizzes (T1) returns them; prep packs and the demo quiz do not.
export type Quiz = { id?: string; title: string; items: QuizItem[]; topic?: string; marks_per_q?: number; total_marks?: number; suggested_minutes?: number }
export type QuizKinds = 'mcq' | 'blank' | 'mixed'
export type QuizRequest = { topic: string; n_items?: number; kinds?: QuizKinds; marks_per_q?: 1 | 2 | 4; upload_id?: string }
// GET /api/v1/quiz-attempts (T4): attempts oldest first, topics by latest attempt.
export type QuizAttempt = { quiz_id: string; score: number; total: number; marks_per_q: number; created_at: string }
export type QuizAttempts = { topics: { topic: string; attempts: QuizAttempt[] }[] }

// Notices (D1), docs/api-contract.md section 4: pasted or shared text, stored as given.
export type NoticeIn = { text: string; source: 'paste' | 'share'; title?: string; url?: string }
export type Notice = { id: string; text: string; source: 'paste' | 'share'; title: string | null; url: string | null; created_at: string }

// D5 prep pack, docs/api-contract.md section 6. links[i]: the notes page for quiz.items[i], or null.
export type NotesLink = { upload_id: string; page: number }
export type PrepPack = { task: { title: string; deadline_utc: string }; quiz_id: string; quiz: Quiz; links: (NotesLink | null)[] }

// PY/TE: POST /pdf/read. text: one entry per page (first 200 pages); a scanned PDF has words 0.
export type PdfRead = { pages: number; words: number; text: string[] }

// T5: GET /api/v1/solves, docs/api-contract.md section 8. The list never carries answers; open one with GET /solve/{id}.
export type SolveItem = { id: string; question: string; status: string; updated_at: string }

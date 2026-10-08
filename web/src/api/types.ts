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

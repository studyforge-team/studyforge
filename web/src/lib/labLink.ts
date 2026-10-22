// Pure on purpose (no '@/' imports) so `node --test` can load it, like lib/errors.ts.
type Final = { answer_md: string }

// question keyword -> ChemLab page (first match wins)
const LAB_LINKS: [RegExp, string][] = [
  [/cstr|stirred tank|continuous stirred/i, '#chemlab'],
  [/distillation|mccabe|reflux|\btrays?\b/i, '#chemlab/mccabe'],
  [/heat exchanger|shell[- ]and[- ]tube|lmtd|\bntu\b/i, '#chemlab/hx'],
]

// The server's fixed off-topic reply (api/app/agent/loop.py OFF_TOPIC_REPLY). `final` carries no kind field, so match its opening.
const REFUSAL = /^\s*I can only help with engineering, science and maths/i

// ChemLab link for a real answer, or undefined (no matching unit, or the answer is a refusal).
export function labLink(question: string, final: Final): string | undefined {
  if (REFUSAL.test(final.answer_md)) return undefined
  return LAB_LINKS.find(([re]) => re.test(question))?.[1] // no input prefill: the question's inputs rarely match the simulator's
}

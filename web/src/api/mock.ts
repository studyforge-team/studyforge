// Scripted stand-in for the backend, used when VITE_API_URL is unset. Same two functions as client.ts.
import type { ResultBody, SolveStart, Step } from './types'

const wait = () => new Promise((r) => setTimeout(r, 300))

const CODE = `import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import brentq

k, tau = 0.2, 10.0  # 1/min, min
X = brentq(lambda x: x - k * tau * (1 - x), 0, 1)  # CSTR balance: X = k*tau*(1-X)
taus = np.linspace(0, 30, 200)
Xs = k * taus / (1 + k * taus)
fig, ax = plt.subplots(figsize=(5, 3.2))
ax.plot(taus, Xs)
ax.axvline(tau, ls="--", c="grey")
ax.set_xlabel("tau (min)")
ax.set_ylabel("conversion X")
ax.set_title("First-order CSTR, k = 0.2 1/min")
fig.tight_layout()
result = {"X": round(float(X), 4), "k": k, "tau": tau}
`

export async function startSolve(question: string): Promise<SolveStart> {
  await wait()
  if (/confirm/i.test(question)) return { solve_id: 'mock', step: { type: 'need_confirm', extracted_text: question } }
  bad = /baddiagram/i.test(question)
  const code = /fail/i.test(question) ? "raise ValueError('demo failure')" : CODE
  return { solve_id: 'mock', step: { type: 'run_python', code, timeout_s: 10 } }
}

let bad = false // ponytail: module flag instead of threading the question through the contract

export async function postResult(_id: string, body: ResultBody): Promise<Step> {
  await wait()
  if (body.error) {
    return {
      type: 'final',
      answer_md: `The computation failed, so there is no verified answer.\n\n\`\`\`\n${body.error}\n\`\`\``,
      numbers: {}, figures: [], sources: [], confidence: 'low',
    }
  }
  const r = body.result as { X: number; k: number; tau: number }
  return {
    type: 'final',
    answer_md:
      `For a first-order reaction in a CSTR, $X = \\frac{k\\tau}{1+k\\tau}$.\n\n` +
      `\n$$\nX = \\frac{${r.k}\\times ${r.tau}}{1+${r.k}\\times ${r.tau}} = ${r.X}\n$$\n\n` +
      `The conversion is **${r.X}** (${(r.X * 100).toFixed(1)} %).`,
    numbers: r as unknown as Record<string, number>,
    figures: body.figures.map((f) => `data:image/png;base64,${f}`),
    diagram_mermaid: bad
      ? 'flowchart LR\n  A -->  ]]]((('
      : `flowchart LR\n  F[Feed C_A0] --> R["CSTR, tau = ${r.tau} min"] --> P["Product, X = ${r.X}"]`,
    sources: [{ title: 'Fogler, Elements of Chemical Reaction Engineering, ch. 5' }],
    confidence: 'high',
  }
}

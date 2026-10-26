// Pure on purpose (no '@/' imports) so `node --test` can load it, like lib/labLink.ts.

// A line that starts a numbered question: "Question 2.", "Q2)", "Problem 3:", "Q. 4".
// ponytail: numbered headings only; a sheet numbered "1." "2." alone stays one question
// (too easy to confuse with steps or list items).
const HEAD = /^\s*(?:question|problem|q)\s*\.?\s*(\d+)\s*[.):-]?\s/im

// A tutorial sheet pasted or photographed as one text -> one text per question, in order.
// Text before the first heading (course title, instructions) is dropped; data lines after a
// heading (tables, Cp expressions) stay with that question. Fewer than two -> [text].
export function splitQuestions(text: string): { label: string; text: string }[] {
  const lines = text.split('\n')
  const starts: { at: number; n: string }[] = []
  lines.forEach((l, i) => {
    const m = HEAD.exec(l + ' ')
    if (m) starts.push({ at: i, n: m[1] })
  })
  if (starts.length < 2) return [{ label: '', text }]
  return starts.map((s, k) => ({
    label: `Question ${s.n}`,
    text: lines.slice(s.at, k + 1 < starts.length ? starts[k + 1].at : lines.length).join('\n').trim(),
  }))
}

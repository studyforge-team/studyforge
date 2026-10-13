// Past-paper topic predictor: pure functions, no I/O. Papers are given oldest first.
// Cost: O(total text length x topics), well under a millisecond for a stack of papers.

export type Topic = { name: string; pattern: RegExp; question: string }

// Chemical engineering subject areas (GATE CH syllabus). A question can match several.
export const TOPICS: readonly Topic[] = [
  {
    name: 'Process calculations',
    pattern: /\b(?:material|mass|energy|component)\s+balances?\b|\bstoichiometr|\brecycle\b|\bpurge\b|\bbypass\b|\blimiting reactant\b|\bexcess air\b/i,
    question: 'Solve a material balance with recycle and purge for a reacting system.',
  },
  {
    name: 'Thermodynamics',
    pattern: /\bthermodynamic|\bentropy\b|\benthalpy\b|\bgibbs\b|\bfugacity\b|\bactivity coefficients?\b|\bvapou?r[- ]liquid equilibri|\bvle\b|\braoult|\bequations? of state\b|\bcarnot\b|\b(?:first|second) law\b|\bclausius\b|\bjoule[- ]thomson\b/i,
    question: "Solve a bubble- or dew-point problem using Raoult's law or activity coefficients.",
  },
  {
    name: 'Fluid mechanics',
    pattern: /\bfluid (?:mechanics|flow|statics|dynamics)\b|\bbernoulli\b|\breynolds\b|\bpressure drop\b|\bviscosit|\bviscomet|\bfriction factor\b|\blaminar\b|\bturbulent\b|\bpumps?\b|\bcompressors?\b|\borifice\b|\bventuri\b|\bnpsh\b|\bpipe flow\b/i,
    question: 'Find the pressure drop and pump power for flow through a pipe using the friction factor.',
  },
  {
    name: 'Mechanical operations',
    pattern: /\bparticles?\b|\bsieve|\bscreening\b|\bfiltration\b|\bfilter cake\b|\bsedimentation\b|\bsettling\b|\bcrushing\b|\bsize reduction\b|\bgrinding\b|\bfluidi[sz]|\bcyclones?\b|\bagitat/i,
    question: 'Estimate a settling velocity or the time for a constant-pressure filtration.',
  },
  {
    name: 'Heat transfer',
    pattern: /\bheat transfer\b|\bconduction\b|\bconvection\b|\bradiation\b|\bheat exchangers?\b|\blmtd\b|\bnusselt\b|\bfins?\b|\bcondens|\bboiling\b|\bevaporators?\b|\bblack ?body\b/i,
    question: 'Size a heat exchanger using the LMTD and the overall heat transfer coefficient.',
  },
  {
    name: 'Mass transfer',
    pattern: /\bmass transfer\b|\bdiffusi|\bfick|\babsorption\b|\bstripping\b|\bextraction\b|\bleaching\b|\bdrying\b|\bdryers?\b|\bhumidif|\badsorption\b|\bsherwood\b|\bcrystalli[sz]/i,
    question: 'Find the flux or the number of transfer units in a gas absorption problem.',
  },
  {
    name: 'Distillation',
    pattern: /\bdistillation\b|\bmccabe|\breflux\b|\brelative volatility\b|\bfenske\b|\bunderwood\b|\btheoretical (?:stages|plates|trays)\b|\bq[- ]line\b|\bponchon\b/i,
    question: 'Find the minimum reflux and the number of theoretical stages with McCabe-Thiele.',
  },
  {
    name: 'Reaction engineering',
    pattern: /\breactors?\b|\bcstr\b|\bpfr\b|\bplug flow\b|\bmixed flow\b|\brate constant\b|\barrhenius\b|\bresidence time\b|\bcatalys|\border of (?:the )?reaction\b|\bkinetics\b|\brtd\b|\bselectivity\b|\bconversion\b/i,
    question: 'Compare CSTR and PFR volumes for a given conversion and rate law.',
  },
  {
    name: 'Process control',
    pattern: /\bprocess control\b|\bcontrollers?\b|\bpid\b|\btransfer functions?\b|\bbode\b|\bnyquist\b|\broot locus\b|\blaplace\b|\bfeedback\b|\bfeedforward\b|\bdamping\b|\bdead time\b|\bcontrol valves?\b|\binstrument|\bthermocouples?\b|\bmanometers?\b/i,
    question: 'Find the step response of a first-order process and tune a PI controller.',
  },
  {
    name: 'Plant design and economics',
    pattern: /\bcosts?\b|\bdepreciation\b|\bnpv\b|\bnet present value\b|\bpayback\b|\bbreak[- ]even\b|\brate of return\b|\bplant design\b|\bprofitab|\bcepci\b/i,
    question: 'Compare two projects by net present value and payback period.',
  },
  {
    name: 'Safety and environment',
    pattern: /\bsafety\b|\bhazop\b|\bhazards?\b|\bexplosi|\bflammab|\brelief valves?\b|\btoxic|\bpollution\b|\beffluents?\b|\bbod\b|\bcod\b|\bwaste ?water\b/i,
    question: 'Identify the hazards of a unit with a HAZOP study.',
  },
  {
    name: 'Chemical technology',
    pattern: /\bfertili[sz]ers?\b|\bammonia\b|\bsulph?uric acid\b|\bcement\b|\bpetroleum\b|\brefin(?:ery|eries|ing)\b|\bcracking\b|\bpolymers?\b|\bsoaps?\b|\bdetergents?\b|\bpulp\b|\bsugar\b|\bchlor[- ]?alkali\b|\bnatural gas\b/i,
    question: 'Describe a manufacturing process with its flow sheet and main engineering problems.',
  },
  {
    name: 'Engineering mathematics',
    pattern: /\bmatri(?:x|ces)\b|\beigen|\bdifferential equations?\b|\bnewton[- ]raphson\b|\bprobabilit|\bfourier\b|\bnumerical methods?\b|\bsimpson\b|\btrapezoid/i,
    question: 'Solve a numerical-methods or differential-equation problem from process engineering.',
  },
]

export type Question = { text: string; marks: number | null }

// A new question starts with "Q1", "Q.1", "Question 1", "1.", "1)" followed by a space.
// "2.5 kg" is not a question number (no space after the dot).
const START = /^\s*(?:Q(?:uestion)?\s*\.?\s*\d{1,3}\s*[.):-]?|\(?\d{1,3}\s*[.)])\s+\S/i
const MARKS = /(\d{1,3})\s*marks?\b|\bmarks?\s*[:=]\s*(\d{1,3})\b|[[(]\s*(\d{1,3})\s*(?:m|marks?)?\s*[\])]\s*$/i

function marksOf(text: string): number | null {
  const m = MARKS.exec(text)
  if (!m) return null
  const n = Number(m[1] ?? m[2] ?? m[3])
  return n > 0 && n <= 200 ? n : null
}

// Section headings ("SECTION B", "Part II", "Unit 3") are not questions and not part of one.
const HEADING = /^(?:section|part|unit|module)\s*[-:]?\s*(?:[a-z]|[ivx]+|\d{1,2})\s*[-:.)]?\s*$/i

export function splitQuestions(paper: string): Question[] {
  const lines = paper
    .replace(/\r\n?/g, '\n')
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !HEADING.test(l))
  const numbered = lines.some((l) => START.test(l))
  const blocks: string[] = []
  for (const line of lines) {
    if (!numbered || START.test(line)) blocks.push(line)
    else if (blocks.length > 0) blocks[blocks.length - 1] += ' ' + line // continuation of the current question
    // else: header text before the first numbered question (time, max marks, instructions): skipped
  }
  return blocks.map((text) => ({ text, marks: marksOf(text) }))
}

export type Trend = 'rising' | 'steady' | 'falling' | 'new'

export type TopicStat = {
  topic: string
  question: string
  papers: number // papers with at least one question on the topic
  questions: number // questions on the topic, all papers
  share: number // 0..1: recency-weighted share of each paper's marks (or questions)
  trend: Trend
}

export type Prediction = {
  papers: number
  questions: number
  usedMarks: boolean // every question showed its marks, so marks were used as weights
  stats: TopicStat[] // most likely first
  unclassified: string[] // questions no topic matched (shown, not hidden)
}

const TREND_STEP = 0.05 // a change of 5 percentage points in share counts as a trend

export function predict(papers: readonly string[]): Prediction {
  const parsed = papers.map(splitQuestions).filter((qs) => qs.length > 0)
  const all = parsed.flat()
  const usedMarks = all.length > 0 && all.every((q) => q.marks !== null)
  const weight = (q: Question) => (usedMarks ? (q.marks as number) : 1)

  // share[t][i]: part of paper i (oldest first) that is about topic t
  const share = TOPICS.map((t) =>
    parsed.map((qs) => {
      const total = qs.reduce((s, q) => s + weight(q), 0)
      const hit = qs.filter((q) => t.pattern.test(q.text)).reduce((s, q) => s + weight(q), 0)
      return total > 0 ? hit / total : 0
    }),
  )
  const recency = parsed.map((_, i) => i + 1) // newest paper counts most
  const recencySum = recency.reduce((a, b) => a + b, 0)

  const stats: TopicStat[] = TOPICS.map((t, k) => {
    const s = share[k]
    const last = s[s.length - 1] ?? 0
    const earlier = s.length > 1 ? s.slice(0, -1).reduce((a, b) => a + b, 0) / (s.length - 1) : last
    const trend: Trend =
      earlier === 0 && last > 0 && s.length > 1
        ? 'new'
        : last - earlier > TREND_STEP
          ? 'rising'
          : earlier - last > TREND_STEP
            ? 'falling'
            : 'steady'
    return {
      topic: t.name,
      question: t.question,
      papers: s.filter((x) => x > 0).length,
      questions: parsed.reduce((n, qs) => n + qs.filter((q) => t.pattern.test(q.text)).length, 0),
      share: recencySum > 0 ? s.reduce((acc, x, i) => acc + x * recency[i], 0) / recencySum : 0,
      trend,
    }
  })
    .filter((st) => st.questions > 0)
    .sort((a, b) => b.share - a.share || b.papers - a.papers || a.topic.localeCompare(b.topic))

  const unclassified = all.filter((q) => !TOPICS.some((t) => t.pattern.test(q.text))).map((q) => q.text)
  return { papers: parsed.length, questions: all.length, usedMarks, stats, unclassified }
}

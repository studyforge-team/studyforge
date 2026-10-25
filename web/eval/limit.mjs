// A cap can arrive as an immediate final, before the polling loop sees the page.
export const limitReached = (bodyText = '', final = null) =>
  /Today.s AI limit is reached/i.test(`${bodyText}\n${final?.answer_md ?? ''}`)

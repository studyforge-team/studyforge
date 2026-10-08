import DOMPurify from 'dompurify'
import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

// htmlLabels off: labels become SVG <text>; HTML labels live in <foreignObject>, which DOMPurify's SVG profile strips
mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', htmlLabels: false, flowchart: { htmlLabels: false } })

export default function Diagram({ src }: { src: string }) {
  const id = 'mmd' + useId().replace(/\W/g, '')
  const [svg, setSvg] = useState<string>()
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let live = true
    ;(async () => {
      await mermaid.parse(src)
      const out = DOMPurify.sanitize((await mermaid.render(id, src)).svg, { USE_PROFILES: { svg: true, svgFilters: true } })
      if (!out.trim()) throw new Error('empty')
      if (live) setSvg(out)
    })().catch(() => {
      document.getElementById('d' + id)?.remove() // mermaid leaves an error node in <body> on failure
      if (live) setFailed(true)
    })
    return () => { live = false }
  }, [src, id])

  if (failed) {
    return (
      <figure>
        <figcaption className="text-sm text-muted-foreground">Diagram couldn't be drawn — here is its source.</figcaption>
        <pre className="overflow-x-auto rounded bg-muted p-2 text-xs"><code>{src}</code></pre>
      </figure>
    )
  }
  if (!svg) return <p>Drawing diagram…</p>
  // Safe: the only dangerouslySetInnerHTML in the app; svg is mermaid strict output re-sanitized by DOMPurify's SVG profile.
  return <div data-testid="diagram" className="overflow-x-auto [&_svg]:max-w-none print:[&_svg]:max-w-full" dangerouslySetInnerHTML={{ __html: svg }} />
}

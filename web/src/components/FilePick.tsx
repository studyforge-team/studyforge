import { useRef } from 'react'
import { Button } from '@/components/ui/button'

const MAX = 10 * 1024 * 1024
export const TOO_BIG = 'That file is over 10 MB. Try a smaller PDF or a cropped photo.'

// Button + hidden file input. Calls onFile only for files within the 10 MB contract limit.
export function FilePick({ label, disabled, onFile, onError, className }: {
  label: string; disabled?: boolean; onFile: (f: File) => void; onError: (m: string) => void; className?: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <>
      <input
        ref={ref} type="file" accept=".pdf,image/*" hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = '' // lets the same file be picked again
          if (!f) return
          if (f.size > MAX) onError(TOO_BIG)
          else onFile(f)
        }}
      />
      <Button type="button" variant="outline" className={className} disabled={disabled} onClick={() => ref.current?.click()}>{label}</Button>
    </>
  )
}

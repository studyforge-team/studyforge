import { useState } from 'react'
import { getPrep, getUploadUrl } from '@/api/client'
import type { NotesLink, PrepPack as Pack } from '@/api/types'
import { friendly, HttpError, PlainError } from '@/lib/errors'
import Quiz from '@/pages/Quiz'

const due = (iso: string) => {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
// the server's own wording is not shown; these say what the student can do
const why = (e: unknown) => {
  const s = e instanceof HttpError ? e.status : 0
  if (s === 404) return 'This prep pack is not one of your tasks.'
  if (s === 503) return 'The prep pack can’t be built right now. Try again in a minute.'
  if (s === 502) return 'Building the prep pack failed. Reload to try again.'
  if (s === 429) return 'Today’s question budget is used up. The prep pack can be built tomorrow.'
  return friendly(e)
}

function NotesButton({ link }: { link: NotesLink }) {
  const [err, setErr] = useState('')
  const open = async () => {
    setErr('')
    const w = window.open('', '_blank') // opened now, while the tap still counts; filled in below
    if (w) w.opener = null // the notes tab gets no handle back to StudyForge
    try {
      const url = await getUploadUrl(link.upload_id)
      if (w) w.location.href = `${url}#page=${link.page}`
      else location.assign(`${url}#page=${link.page}`)
    } catch (e) {
      w?.close()
      setErr(e instanceof HttpError && e.status === 404 ? 'These notes were deleted.' : friendly(e))
    }
  }
  return (
    <p className="mt-3 text-sm">
      <button type="button" className="inline-flex min-h-11 items-center text-primary underline" onClick={() => void open()}>From your notes: page {link.page}</button>
      {err && <span role="alert" className="ml-2 text-destructive">{err}</span>}
    </p>
  )
}

// D5: #prep/<task key>. The server builds the pack the first time it is opened (5 questions from the
// student's notes, each linked to its page); the quiz itself runs exactly like the Quiz page.
export default function PrepPack({ taskKey }: { taskKey: string }) {
  const [pack, setPack] = useState<Pack>()
  const load = async (onSlow: () => void) => {
    try {
      const p = await getPrep(taskKey, onSlow)
      setPack(p)
      return { ...p.quiz, id: p.quiz_id }
    } catch (e) {
      throw new PlainError(why(e)) // the Quiz page shows a PlainError's text as is
    }
  }
  return (
    <>
      {pack && (
        <p className="mx-auto max-w-3xl px-4 pt-6 text-sm text-muted-foreground">
          {pack.task.title}{due(pack.task.deadline_utc) && ` · due ${due(pack.task.deadline_utc)}`}
        </p>
      )}
      <Quiz load={load} heading="Prep pack" extra={(i) => { const l = pack?.links[i]; return l ? <NotesButton link={l} /> : null }} />
    </>
  )
}

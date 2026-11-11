import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'

import { ApiError } from '../api'
import { useCreateNote } from '../hooks'
import { Alert } from './Alert'

export function NoteComposer({ maxChars }: { maxChars: number }) {
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const createNote = useCreateNote()

  const tooLong = body.length > maxChars
  const canSave = body.trim().length > 0 && !tooLong && !createNote.isPending
  const error = createNote.error instanceof ApiError ? createNote.error : null
  const existingId = error?.code === 'duplicate' ? String(error.details.existing_source_id ?? '') : ''

  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    if (!canSave) return
    setSaved(null)
    createNote.mutate(
      { body, title },
      {
        onSuccess: (source) => {
          setTitle('')
          setBody('')
          setSaved(source.title)
        },
      },
    )
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit()
  }

  return (
    <form onSubmit={submit} className="flex h-full flex-col gap-3">
      <input
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Title (optional)"
        maxLength={300}
        aria-label="Note title"
        className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm font-medium outline-none placeholder:text-stone-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
      />
      <textarea
        value={body}
        onChange={(e) => {
          setBody(e.target.value)
          if (saved) setSaved(null)
        }}
        onKeyDown={onKeyDown}
        placeholder="What's on your mind? Ideas, meeting notes, things to remember…"
        aria-label="Note body"
        rows={9}
        className="min-h-48 flex-1 resize-y rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm leading-relaxed outline-none placeholder:text-stone-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
      />
      {error && (
        <Alert>
          {error.message}{' '}
          {existingId && (
            <Link to={`/sources/${existingId}`} className="font-medium underline">
              Open it
            </Link>
          )}
        </Alert>
      )}
      {saved && <Alert tone="info">Saved “{saved}”. It'll be searchable in a moment.</Alert>}
      <div className="flex items-center justify-between gap-3">
        <span className={`text-xs ${tooLong ? 'text-rose-700' : 'text-stone-400'}`}>
          {tooLong
            ? `${body.length.toLocaleString()} / ${maxChars.toLocaleString()} characters — upload long text as a file`
            : '⌘/Ctrl + Enter to save'}
        </span>
        <button
          type="submit"
          disabled={!canSave}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {createNote.isPending ? 'Saving…' : 'Save note'}
        </button>
      </div>
    </form>
  )
}

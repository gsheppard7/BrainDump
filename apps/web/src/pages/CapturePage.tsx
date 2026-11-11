import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { Alert } from '../components/Alert'
import { FileUploader } from '../components/FileUploader'
import { NoteComposer } from '../components/NoteComposer'
import { SourceRow } from '../components/SourceRow'
import { useMeta, useSources } from '../hooks'

const DEFAULT_MAX_BYTES = 20 * 1024 * 1024

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col rounded-2xl border border-stone-200 bg-white/60 p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-stone-700">{title}</h2>
      <div className="flex-1">{children}</div>
    </section>
  )
}

export function CapturePage() {
  const meta = useMeta()
  const recent = useSources({ limit: 8 })

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Capture</h1>
        <p className="mt-1 text-sm text-stone-500">Dump it here; find it later.</p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Write a note">
          <NoteComposer maxChars={meta.data?.max_note_chars ?? 200_000} />
        </Card>
        <Card title="Upload files">
          <FileUploader
            maxBytes={meta.data?.max_upload_bytes ?? DEFAULT_MAX_BYTES}
            extensions={meta.data?.accepted_extensions}
          />
        </Card>
      </div>

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-stone-700">Recent captures</h2>
          <Link to="/library" className="text-sm text-indigo-600 hover:underline">
            View library →
          </Link>
        </div>
        {recent.isError ? (
          <Alert>{recent.error.message}</Alert>
        ) : recent.isPending ? (
          <p className="px-3 py-6 text-sm text-stone-500">Loading…</p>
        ) : recent.data.items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-stone-300 px-3 py-6 text-center text-sm text-stone-500">
            Nothing here yet. Write a note or upload a file to get started.
          </p>
        ) : (
          <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 bg-white">
            {recent.data.items.map((s) => (
              <SourceRow key={s.id} source={s} />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

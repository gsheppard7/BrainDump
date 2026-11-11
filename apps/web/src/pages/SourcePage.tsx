import { useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { Alert } from '../components/Alert'
import { KindTag } from '../components/KindTag'
import { Spinner, StatusBadge } from '../components/StatusBadge'
import { useDeleteSource, useRetrySource, useSource } from '../hooks'
import { formatBytes, formatDateTime } from '../lib/format'
import { highlightTerms, queryTerms } from '../lib/highlight'
import type { SourceDetail } from '../types'

export function SourcePage() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const source = useSource(id)

  if (source.isError) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink query={params.get('q')} />
        <Alert>{source.error.message}</Alert>
      </div>
    )
  }
  if (source.isPending) {
    return (
      <p className="flex items-center gap-2 text-sm text-stone-500">
        <Spinner /> Loading…
      </p>
    )
  }
  return <SourceView source={source.data} query={params.get('q')} chunkParam={params.get('chunk')} />
}

function BackLink({ query }: { query: string | null }) {
  const to = query ? `/library?${new URLSearchParams({ q: query })}` : '/library'
  return (
    <Link to={to} className="text-sm text-indigo-600 hover:underline">
      ← {query ? 'Back to results' : 'Library'}
    </Link>
  )
}

function SourceView({ source, query, chunkParam }: { source: SourceDetail; query: string | null; chunkParam: string | null }) {
  const navigate = useNavigate()
  const del = useDeleteSource()
  const retry = useRetrySource()

  const facts = [
    ['Type', source.kind === 'note' ? 'Note' : (source.file_type ?? 'File').toUpperCase()],
    ['Filename', source.original_filename],
    ['Size', formatBytes(source.size_bytes)],
    ['Pages', source.page_count?.toString()],
    ['Characters', source.char_count?.toLocaleString()],
    ['Added', formatDateTime(source.created_at)],
    ['Processed', source.processed_at ? formatDateTime(source.processed_at) : null],
    ['Meaning index', source.embedding_status === 'done' ? 'Ready' : source.embedding_status === 'pending' ? 'Pending' : null],
  ].filter((f): f is [string, string] => Boolean(f[1]))

  const onDelete = () => {
    if (!window.confirm(`Delete “${source.title}”? This removes the file and its search index.`)) return
    del.mutate(source.id, { onSuccess: () => navigate('/library', { replace: true }) })
  }

  return (
    <article className="flex flex-col gap-6">
      <BackLink query={query} />
      <header className="flex flex-col gap-3">
        <div className="flex items-start gap-3">
          <KindTag kind={source.kind} fileType={source.file_type} />
          <h1 className="flex-1 text-2xl font-semibold tracking-tight break-words">{source.title}</h1>
          <StatusBadge status={source.status} />
        </div>
        <dl className="flex flex-wrap gap-x-6 gap-y-1 text-xs">
          {facts.map(([k, v]) => (
            <div key={k} className="flex gap-1.5">
              <dt className="text-stone-500">{k}</dt>
              <dd className="text-stone-800">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="flex gap-2">
          {source.status === 'failed' && (
            <button
              type="button"
              onClick={() => retry.mutate(source.id)}
              disabled={retry.isPending}
              className="rounded-lg bg-stone-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-stone-700 disabled:opacity-50"
            >
              Retry processing
            </button>
          )}
          <button
            type="button"
            onClick={onDelete}
            disabled={del.isPending}
            className="rounded-lg border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:border-rose-300 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
        {del.error && <Alert>{del.error.message}</Alert>}
        {retry.error && <Alert>{retry.error.message}</Alert>}
      </header>

      {source.status === 'failed' && (
        <Alert>
          <strong className="font-semibold">Processing failed.</strong> {source.error_message}
        </Alert>
      )}
      {(source.status === 'pending' || source.status === 'processing') && (
        <Alert tone="info">
          <span className="flex items-center gap-2">
            <Spinner />
            {source.status === 'pending' ? 'Queued for processing…' : 'Extracting and indexing text…'} This page updates automatically.
          </span>
        </Alert>
      )}

      {source.text_content && <SourceText source={source} query={query} chunkParam={chunkParam} />}
    </article>
  )
}

function SourceText({ source, query, chunkParam }: { source: SourceDetail; query: string | null; chunkParam: string | null }) {
  const focusRef = useRef<HTMLElement>(null)
  const text = source.text_content ?? ''
  const chunk = chunkParam !== null ? source.chunks.find((c) => c.ordinal === Number(chunkParam)) : undefined
  const terms = useMemo(() => (query ? queryTerms(query) : []), [query])

  useEffect(() => {
    focusRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [chunk?.id])

  const render = (segment: string, keyPrefix: string) =>
    highlightTerms(segment, terms).map((p, i) =>
      p.highlight ? <mark key={`${keyPrefix}${i}`}>{p.text}</mark> : <span key={`${keyPrefix}${i}`}>{p.text}</span>,
    )

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
      {chunk && (
        <p className="mb-4 text-xs text-stone-500">
          Showing the best match for “{query}”{chunk.page ? ` on page ${chunk.page}` : ''}, highlighted below.
        </p>
      )}
      <div className="font-[ui-serif,Georgia,serif] text-[15px] leading-7 whitespace-pre-wrap text-stone-800 break-words">
        {chunk ? (
          <>
            {render(text.slice(0, chunk.char_start), 'a')}
            <span ref={focusRef} className="box-decoration-clone rounded bg-indigo-50 px-0.5">
              {render(text.slice(chunk.char_start, chunk.char_end), 'b')}
            </span>
            {render(text.slice(chunk.char_end), 'c')}
          </>
        ) : (
          render(text, 'a')
        )}
      </div>
    </section>
  )
}

import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Alert } from '../components/Alert'
import { KindTag } from '../components/KindTag'
import { SourceRow } from '../components/SourceRow'
import { Spinner } from '../components/StatusBadge'
import { useDebounced, useMeta, useSearch, useSources } from '../hooks'
import { formatRelative } from '../lib/format'
import type { SearchHit, SourceStatus } from '../types'

const FILTERS: { label: string; value?: SourceStatus }[] = [
  { label: 'All' },
  { label: 'Ready', value: 'ready' },
  { label: 'Processing', value: 'processing' },
  { label: 'Queued', value: 'pending' },
  { label: 'Failed', value: 'failed' },
]

export function LibraryPage() {
  const [params, setParams] = useSearchParams()
  const urlQuery = params.get('q') ?? ''
  const [input, setInput] = useState(urlQuery)
  const [prevUrlQuery, setPrevUrlQuery] = useState(urlQuery)
  const debounced = useDebounced(input, 250)

  if (urlQuery !== prevUrlQuery) {
    setPrevUrlQuery(urlQuery)
    if (urlQuery !== input.trim()) setInput(urlQuery)
  }

  useEffect(() => {
    if (debounced !== input || debounced.trim() === urlQuery) return
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (debounced.trim()) next.set('q', debounced.trim())
        else next.delete('q')
        return next
      },
      { replace: true },
    )
  }, [debounced, input, urlQuery, setParams])

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
        <p className="mt-1 text-sm text-stone-500">Everything you've captured, searchable.</p>
      </div>

      <div>
        <div className="relative">
          <svg className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-stone-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" strokeLinecap="round" />
          </svg>
          <input
            type="search"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder='Search notes and files — try "sourdough" or "restart modem"'
            aria-label="Search your library"
            autoFocus
            maxLength={500}
            className="w-full rounded-xl border border-stone-200 bg-white py-3 pr-4 pl-10 text-sm shadow-sm outline-none placeholder:text-stone-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
        </div>
        <SearchModeNote />
      </div>

      {urlQuery ? <SearchResults query={urlQuery} /> : <BrowseList />}
    </div>
  )
}

function SearchModeNote() {
  const meta = useMeta()
  const semantic = meta.data?.capabilities.semantic_search ?? false
  const pending = meta.data?.index.semantic_pending ?? 0
  return (
    <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-stone-500">
      <span className="rounded-full bg-stone-200/70 px-2 py-0.5 font-medium text-stone-700">
        {semantic ? 'Hybrid search' : 'Keyword search'}
      </span>
      {semantic
        ? 'Matches exact words and related meaning, computed locally.'
        : "Matches words and their variants, not meaning — local AI isn't available."}{' '}
      Use "quotes" for phrases and -word to exclude.
      {semantic && pending > 0 && (
        <span className="text-amber-700">
          Indexing meaning for {pending} source{pending === 1 ? '' : 's'}…
        </span>
      )}
    </p>
  )
}

function SearchResults({ query }: { query: string }) {
  const search = useSearch(query)

  if (search.isError) return <Alert>{search.error.message}</Alert>
  if (!search.data) {
    return (
      <p className="flex items-center gap-2 px-1 text-sm text-stone-500">
        <Spinner /> Searching…
      </p>
    )
  }
  const data = search.data
  if (!data.query_has_terms) {
    return <Alert tone="warning">That query only contains very common words. Try something more specific.</Alert>
  }
  if (data.hits.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-stone-300 px-3 py-8 text-center text-sm text-stone-500">
        No matches for “{data.query}”. Sources still processing won't appear until they're ready.
      </p>
    )
  }
  return (
    <section aria-label="Search results" className={search.isFetching ? 'opacity-70 transition' : 'transition'}>
      {data.notice && (
        <div className="mb-3">
          <Alert tone="warning">{data.notice}</Alert>
        </div>
      )}
      <p className="mb-2 px-1 text-xs text-stone-500">
        {data.total} matching source{data.total === 1 ? '' : 's'}
      </p>
      <ul className="flex flex-col gap-2">
        {data.hits.map((hit) => (
          <SearchResultItem key={hit.source_id} hit={hit} query={data.query} />
        ))}
      </ul>
    </section>
  )
}

function SearchResultItem({ hit, query }: { hit: SearchHit; query: string }) {
  const link = `/sources/${hit.source_id}?${new URLSearchParams({ q: query, chunk: String(hit.chunk_ordinal) })}`
  return (
    <li>
      <Link
        to={link}
        className="block rounded-xl border border-stone-200 bg-white px-4 py-3 shadow-sm transition hover:border-indigo-300 hover:shadow"
      >
        <div className="flex items-center gap-3">
          <KindTag kind={hit.kind} fileType={hit.file_type} />
          <span className="truncate font-medium">{hit.title}</span>
          {hit.match_reasons.map((reason) => (
            <span
              key={reason}
              className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-600"
              title={reason === 'keyword' ? 'Contains your search words' : 'Related in meaning'}
            >
              {reason === 'keyword' ? 'words' : 'meaning'}
            </span>
          ))}
          <span className="ml-auto shrink-0 text-xs text-stone-500">
            {[hit.page ? `p. ${hit.page}` : null, hit.match_count > 1 ? `${hit.match_count} passages` : null, formatRelative(hit.created_at)]
              .filter(Boolean)
              .join(' · ')}
          </span>
        </div>
        <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-stone-600">
          {hit.snippet.map((part, i) => (part.highlight ? <mark key={i}>{part.text}</mark> : <span key={i}>{part.text}</span>))}
        </p>
      </Link>
    </li>
  )
}

function BrowseList() {
  const [filter, setFilter] = useState<SourceStatus | undefined>()
  const sources = useSources({ status: filter, limit: 200 })

  return (
    <section>
      <div className="mb-3 flex flex-wrap gap-1" role="tablist" aria-label="Filter by status">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            role="tab"
            aria-selected={filter === f.value}
            onClick={() => setFilter(f.value)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              filter === f.value ? 'bg-stone-900 text-white' : 'bg-stone-200/60 text-stone-600 hover:bg-stone-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      {sources.isError ? (
        <Alert>{sources.error.message}</Alert>
      ) : sources.isPending ? (
        <p className="px-1 text-sm text-stone-500">Loading…</p>
      ) : sources.data.items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-stone-300 px-3 py-8 text-center text-sm text-stone-500">
          {filter ? 'No sources with this status.' : 'Your library is empty. '}
          {!filter && (
            <Link to="/" className="text-indigo-600 hover:underline">
              Capture something
            </Link>
          )}
        </p>
      ) : (
        <>
          <p className="mb-2 px-1 text-xs text-stone-500">
            {sources.data.total} source{sources.data.total === 1 ? '' : 's'}
            {sources.data.total > sources.data.items.length && ` (showing ${sources.data.items.length})`}
          </p>
          <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 bg-white">
            {sources.data.items.map((s) => (
              <SourceRow key={s.id} source={s} />
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

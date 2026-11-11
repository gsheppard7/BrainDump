import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Alert } from '../components/Alert'
import { BrainCanvas } from '../components/BrainCanvas'
import { KindTag } from '../components/KindTag'
import { Spinner } from '../components/StatusBadge'
import { useGraph } from '../hooks'
import { formatDateTime, formatRelative } from '../lib/format'

export function BrainPage() {
  const graph = useGraph()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const selected = useMemo(
    () => graph.data?.nodes.find((n) => n.id === selectedId) ?? null,
    [graph.data, selectedId],
  )
  const neighbors = useMemo(() => {
    if (!graph.data || !selectedId) return []
    const { edges, nodes } = graph.data
    const byId = new Map(nodes.map((n) => [n.id, n]))
    return edges
      .filter((e) => e.source === selectedId || e.target === selectedId)
      .map((e) => {
        const otherId = e.source === selectedId ? e.target : e.source
        return { node: byId.get(otherId)!, weight: e.weight }
      })
      .filter((row) => row.node)
      .sort((a, b) => b.weight - a.weight)
  }, [graph.data, selectedId])

  if (graph.isLoading) {
    return (
      <p className="flex items-center gap-2 text-sm text-stone-500">
        <Spinner /> Mapping your knowledge base…
      </p>
    )
  }

  if (graph.isError || !graph.data) {
    return <Alert>Couldn't load the brain map.</Alert>
  }

  const { nodes, edges, stats } = graph.data

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Brain</h1>
          <p className="mt-1 max-w-2xl text-sm text-stone-500">
            A living map of your knowledge base. Each node is a note or file; lines connect sources that
            share meaning. Drag to rearrange, click to inspect, double-click to open.
          </p>
        </div>
        <dl className="flex flex-wrap gap-4 text-sm">
          <Stat label="Sources" value={stats.sources} />
          <Stat label="Connections" value={stats.connections} />
          <Stat label="Indexed" value={stats.indexed} />
          {stats.pending > 0 && <Stat label="Still learning" value={stats.pending} accent />}
        </dl>
      </div>

      {nodes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-16 text-center">
          <p className="text-sm font-medium text-stone-700">Nothing to map yet</p>
          <p className="mt-1 text-sm text-stone-500">
            Capture a few notes or upload files, then come back — the brain grows as you add knowledge.
          </p>
          <Link to="/" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline">
            Go to Capture
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_260px]">
          <BrainCanvas
            nodes={nodes}
            edges={edges}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <aside className="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm lg:self-start">
            {selected ? (
              <div className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <KindTag kind={selected.kind} fileType={selected.file_type} />
                    <h2 className="mt-2 text-base font-semibold text-stone-900">{selected.title}</h2>
                  </div>
                </div>
                <dl className="grid grid-cols-2 gap-2 text-xs text-stone-500">
                  <div>
                    <dt>Captured</dt>
                    <dd className="font-medium text-stone-700">{formatRelative(selected.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Size</dt>
                    <dd className="font-medium text-stone-700">
                      {selected.chunk_count} chunk{selected.chunk_count === 1 ? '' : 's'} ·{' '}
                      {selected.char_count.toLocaleString()} chars
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt>Meaning index</dt>
                    <dd className="font-medium text-stone-700">
                      {selected.embedding_status === 'done'
                        ? 'Ready — connected by meaning'
                        : selected.embedding_status === 'pending'
                          ? 'Still embedding…'
                          : 'Not indexed yet'}
                    </dd>
                  </div>
                </dl>
                {neighbors.length > 0 ? (
                  <div>
                    <h3 className="mb-1 text-xs font-semibold tracking-wide text-stone-500 uppercase">
                      Related
                    </h3>
                    <ul className="divide-y divide-stone-100 rounded-lg border border-stone-100">
                      {neighbors.map(({ node, weight }) => (
                        <li key={node.id}>
                          <button
                            type="button"
                            onClick={() => setSelectedId(node.id)}
                            className="flex w-full items-center justify-between gap-2 px-2.5 py-2 text-left text-sm hover:bg-stone-50"
                          >
                            <span className="truncate font-medium text-stone-800">{node.title}</span>
                            <span className="shrink-0 text-xs text-stone-400">
                              {Math.round(weight * 100)}%
                            </span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">
                    No strong connections yet. Add more notes on related topics and they'll start linking
                    up.
                  </p>
                )}
                <Link
                  to={`/sources/${selected.id}`}
                  className="rounded-lg bg-indigo-600 px-3 py-2 text-center text-sm font-medium text-white hover:bg-indigo-500"
                >
                  Open source
                </Link>
                <p className="text-[11px] text-stone-400">
                  Added {formatDateTime(selected.created_at)}. Double-click a node to open it.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3 text-sm text-stone-500">
                <p className="font-medium text-stone-800">How to read this</p>
                <ul className="list-disc space-y-1.5 pl-4 text-xs leading-relaxed">
                  <li>
                    <span className="font-medium text-indigo-700">Lavender</span> nodes are notes;{' '}
                    <span className="font-medium text-emerald-700">mint</span> nodes are files.
                  </li>
                  <li>Larger nodes hold more text. Thicker lines mean a stronger meaning overlap.</li>
                  <li>Amber dots mark sources still being indexed into the meaning layer.</li>
                  <li>Capture more and the map densifies — that's the brain forming.</li>
                </ul>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, accent = false }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="min-w-16">
      <dt className="text-[11px] tracking-wide text-stone-400 uppercase">{label}</dt>
      <dd className={`text-lg font-semibold tabular-nums ${accent ? 'text-amber-600' : 'text-stone-800'}`}>
        {value}
      </dd>
    </div>
  )
}

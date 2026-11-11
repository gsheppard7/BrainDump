import { Link } from 'react-router-dom'

import { formatBytes, formatRelative } from '../lib/format'
import type { SourceSummary } from '../types'
import { KindTag } from './KindTag'
import { StatusBadge } from './StatusBadge'

export function SourceRow({ source }: { source: SourceSummary }) {
  const meta = [
    source.original_filename,
    source.page_count ? `${source.page_count} page${source.page_count === 1 ? '' : 's'}` : null,
    formatBytes(source.size_bytes),
    formatRelative(source.created_at),
  ].filter(Boolean)

  return (
    <li>
      <Link
        to={`/sources/${source.id}`}
        className="flex items-start gap-3 rounded-lg px-3 py-3 transition hover:bg-stone-100 focus-visible:bg-stone-100 focus-visible:outline-none"
      >
        <KindTag kind={source.kind} fileType={source.file_type} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-stone-900">{source.title}</span>
          </div>
          <div className="mt-0.5 truncate text-xs text-stone-500">{meta.join(' · ')}</div>
          {source.status === 'failed' && source.error_message && (
            <div className="mt-1 text-xs text-rose-700">{source.error_message}</div>
          )}
        </div>
        <StatusBadge status={source.status} />
      </Link>
    </li>
  )
}

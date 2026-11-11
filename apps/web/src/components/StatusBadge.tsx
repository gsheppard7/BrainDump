import type { SourceStatus } from '../types'

const STYLES: Record<SourceStatus, { label: string; className: string }> = {
  pending: { label: 'Queued', className: 'bg-stone-100 text-stone-600 ring-stone-200' },
  processing: { label: 'Processing', className: 'bg-sky-50 text-sky-700 ring-sky-200' },
  ready: { label: 'Ready', className: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
  failed: { label: 'Failed', className: 'bg-rose-50 text-rose-700 ring-rose-200' },
}

export function StatusBadge({ status }: { status: SourceStatus }) {
  const { label, className } = STYLES[status]
  const busy = status === 'pending' || status === 'processing'
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
      role="status"
    >
      {busy && <Spinner />}
      {label}
    </span>
  )
}

export function Spinner({ className = 'size-3' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}

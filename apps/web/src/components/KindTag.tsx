import type { FileType, SourceKind } from '../types'

const LABELS: Record<string, { label: string; className: string }> = {
  note: { label: 'Note', className: 'bg-indigo-50 text-indigo-700' },
  pdf: { label: 'PDF', className: 'bg-rose-50 text-rose-700' },
  markdown: { label: 'MD', className: 'bg-violet-50 text-violet-700' },
  text: { label: 'TXT', className: 'bg-stone-100 text-stone-700' },
}

export function KindTag({ kind, fileType }: { kind: SourceKind; fileType: FileType | null }) {
  const { label, className } = LABELS[kind === 'note' ? 'note' : (fileType ?? 'text')]!
  return (
    <span
      className={`inline-flex w-11 shrink-0 justify-center rounded-md py-1 text-[11px] font-semibold tracking-wide ${className}`}
    >
      {label}
    </span>
  )
}

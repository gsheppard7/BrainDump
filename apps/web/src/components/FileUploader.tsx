import { useRef, useState, type DragEvent } from 'react'
import { Link } from 'react-router-dom'

import { api, ApiError } from '../api'
import { useInvalidateSources } from '../hooks'
import { DEFAULT_EXTENSIONS, precheckFile } from '../lib/files'
import { formatBytes } from '../lib/format'
import { Spinner } from './StatusBadge'

interface UploadItem {
  key: string
  name: string
  size: number
  progress: number
  state: 'uploading' | 'error'
  error?: string
  existingId?: string
}

let counter = 0

export function FileUploader({ maxBytes, extensions = DEFAULT_EXTENSIONS }: { maxBytes: number; extensions?: string[] }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [items, setItems] = useState<UploadItem[]>([])
  const invalidate = useInvalidateSources()

  const update = (key: string, patch: Partial<UploadItem>) =>
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)))
  const remove = (key: string) => setItems((prev) => prev.filter((it) => it.key !== key))

  const handleFiles = async (files: FileList | File[]) => {
    const queued = Array.from(files).map((file) => {
      const problem = precheckFile(file, maxBytes, extensions)
      const item: UploadItem = {
        key: `u${++counter}`,
        name: file.name,
        size: file.size,
        progress: 0,
        state: problem ? 'error' : 'uploading',
        error: problem ?? undefined,
      }
      return { file, item, ok: !problem }
    })
    setItems((prev) => [...queued.map((q) => q.item), ...prev])

    for (const { file, item, ok } of queued) {
      if (!ok) continue
      try {
        await api.uploadFile(file, (p) => update(item.key, { progress: p }))
        remove(item.key)
        await invalidate()
      } catch (err) {
        const apiErr = err instanceof ApiError ? err : null
        update(item.key, {
          state: 'error',
          error: apiErr?.message ?? 'Upload failed.',
          existingId: apiErr?.code === 'duplicate' ? String(apiErr.details.existing_source_id) : undefined,
        })
      }
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) void handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="flex h-full flex-col gap-3">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex min-h-48 flex-1 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? 'border-indigo-400 bg-indigo-50' : 'border-stone-300 bg-white hover:border-stone-400 hover:bg-stone-50'
        }`}
      >
        <svg className="size-8 text-stone-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="text-sm font-medium text-stone-700">Drop files here or click to browse</span>
        <span className="text-xs text-stone-500">PDF, Markdown, or plain text · up to {formatBytes(maxBytes)}</span>
      </button>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={extensions.join(',')}
        className="hidden"
        data-testid="file-input"
        onChange={(e) => {
          if (e.target.files?.length) void handleFiles(e.target.files)
          e.target.value = ''
        }}
      />
      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.map((it) => (
            <li
              key={it.key}
              className={`rounded-lg border px-3 py-2 text-sm ${it.state === 'error' ? 'border-rose-200 bg-rose-50' : 'border-stone-200 bg-white'}`}
            >
              <div className="flex items-center gap-2">
                {it.state === 'uploading' && <Spinner className="size-3.5 text-indigo-600" />}
                <span className="truncate font-medium">{it.name}</span>
                <span className="shrink-0 text-xs text-stone-500">{formatBytes(it.size)}</span>
                {it.state === 'uploading' ? (
                  <span className="ml-auto text-xs text-stone-500">Uploading {Math.round(it.progress * 100)}%</span>
                ) : (
                  <button type="button" onClick={() => remove(it.key)} className="ml-auto text-xs text-stone-500 hover:text-stone-900" aria-label={`Dismiss ${it.name}`}>
                    Dismiss
                  </button>
                )}
              </div>
              {it.state === 'uploading' && (
                <div className="mt-2 h-1 overflow-hidden rounded bg-stone-100">
                  <div className="h-full bg-indigo-500 transition-all" style={{ width: `${it.progress * 100}%` }} />
                </div>
              )}
              {it.error && (
                <p className="mt-1 text-rose-700" role="alert">
                  {it.error}{' '}
                  {it.existingId && (
                    <Link to={`/sources/${it.existingId}`} className="font-medium underline">
                      Open it
                    </Link>
                  )}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

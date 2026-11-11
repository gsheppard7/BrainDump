import type {
  AskEvent,
  AskMode,
  Meta,
  SearchResponse,
  SourceDetail,
  SourceList,
  SourceStatus,
  SourceSummary,
} from './types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

const FALLBACK_MESSAGES: Record<number, string> = {
  413: 'That file is too large to upload.',
  502: "BrainDump's server isn't responding. Is the API running?",
  503: "BrainDump's server isn't responding. Is the API running?",
  504: 'The server took too long to respond.',
}

export function toApiError(status: number, bodyText: string): ApiError {
  try {
    const body = JSON.parse(bodyText) as { error?: { code?: string; message?: string; details?: Record<string, unknown> } }
    if (body.error?.message) {
      return new ApiError(status, body.error.code ?? 'error', body.error.message, body.error.details ?? {})
    }
  } catch {
    // Non-JSON error bodies (e.g. from a proxy) fall through to a generic message.
  }
  return new ApiError(status, 'http_error', FALLBACK_MESSAGES[status] ?? `Request failed (${status}).`)
}

const networkError = () =>
  new ApiError(0, 'network_error', "Can't reach the BrainDump server. Check that the API is running.")

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch {
    throw networkError()
  }
  if (!res.ok) throw toApiError(res.status, await res.text())
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function readNdjson(body: ReadableStream<Uint8Array>, onLine: (line: string) => void) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let newline: number
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (line) onLine(line)
    }
  }
  if (buffer.trim()) onLine(buffer.trim())
}

export interface ListParams {
  status?: SourceStatus
  limit?: number
}

export const api = {
  meta: () => request<Meta>('/api/meta'),

  listSources: ({ status, limit = 50 }: ListParams = {}) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (status) params.set('status', status)
    return request<SourceList>(`/api/sources?${params}`)
  },

  getSource: (id: string) => request<SourceDetail>(`/api/sources/${encodeURIComponent(id)}`),

  search: (q: string) => request<SearchResponse>(`/api/search?${new URLSearchParams({ q, limit: '30' })}`),

  createNote: (body: string, title?: string) =>
    request<SourceSummary>('/api/sources/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body, title: title?.trim() || null }),
    }),

  deleteSource: (id: string) =>
    request<void>(`/api/sources/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  retrySource: (id: string) =>
    request<SourceSummary>(`/api/sources/${encodeURIComponent(id)}/retry`, { method: 'POST' }),

  /** Streams newline-delimited JSON events from POST /api/ask. */
  ask: async (question: string, mode: AskMode, onEvent: (e: AskEvent) => void, signal?: AbortSignal) => {
    let res: Response
    try {
      res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, mode }),
        signal,
      })
    } catch (err) {
      if (signal?.aborted) return
      throw err instanceof ApiError ? err : networkError()
    }
    if (!res.ok || !res.body) throw toApiError(res.status, await res.text())
    await readNdjson(res.body, (line) => onEvent(JSON.parse(line) as AskEvent))
  },

  /** XHR instead of fetch so we can report upload progress. */
  uploadFile: (file: File, onProgress?: (fraction: number) => void) =>
    new Promise<SourceSummary>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/sources/files')
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress?.(e.loaded / e.total)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText) as SourceSummary)
        else reject(toApiError(xhr.status, xhr.responseText))
      }
      xhr.onerror = () => reject(networkError())
      const form = new FormData()
      form.append('file', file)
      xhr.send(form)
    }),
}

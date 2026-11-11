export type SourceKind = 'note' | 'file'
export type FileType = 'pdf' | 'markdown' | 'text'
export type SourceStatus = 'pending' | 'processing' | 'ready' | 'failed'

export interface SourceSummary {
  id: string
  kind: SourceKind
  file_type: FileType | null
  title: string
  original_filename: string | null
  size_bytes: number
  status: SourceStatus
  embedding_status: 'pending' | 'done' | null
  error_code: string | null
  error_message: string | null
  char_count: number | null
  page_count: number | null
  created_at: string
  processed_at: string | null
}

export interface ChunkInfo {
  id: string
  ordinal: number
  char_start: number
  char_end: number
  page: number | null
}

export interface SourceDetail extends SourceSummary {
  text_content: string | null
  chunks: ChunkInfo[]
}

export interface SourceList {
  items: SourceSummary[]
  total: number
}

export interface SnippetPart {
  text: string
  highlight: boolean
}

export interface SearchHit {
  source_id: string
  title: string
  kind: SourceKind
  file_type: FileType | null
  created_at: string
  chunk_id: string
  chunk_ordinal: number
  page: number | null
  rank: number
  match_count: number
  match_reasons: MatchReason[]
  snippet: SnippetPart[]
}

export type MatchReason = 'keyword' | 'semantic'

export interface SearchResponse {
  query: string
  mode: 'keyword' | 'hybrid'
  semantic_available: boolean
  notice: string | null
  total: number
  query_has_terms: boolean
  hits: SearchHit[]
}

export interface Meta {
  status: 'ok' | 'degraded'
  database: boolean
  max_upload_bytes: number
  max_note_chars: number
  accepted_extensions: string[]
  capabilities: {
    keyword_search: boolean
    semantic_search: boolean
    grounded_chat: boolean
    memory_extraction: boolean
  }
  ai: {
    provider: string
    location: string
    embedding_model: string | null
    chat_model: string | null
    reachable: boolean
    message: string | null
  }
  index: {
    ready_sources: number
    semantic_indexed: number
    semantic_pending: number
  }
}

export type AskMode = 'recall' | 'plan' | 'report' | 'brainstorm'

export interface AskPassage {
  n: number
  source_id: string
  chunk_id: string
  chunk_ordinal: number
  page: number | null
  title: string
  kind: SourceKind
  file_type: FileType | null
  created_at: string
  excerpt: string
  match_reasons: MatchReason[]
}

export type AskEvent =
  | { type: 'meta'; model: string; location: string; notice: string | null }
  | { type: 'context'; passages: AskPassage[] }
  | { type: 'delta'; text: string }
  | { type: 'done'; citations: number[]; grounded: boolean }
  | { type: 'error'; message: string }

export const isInFlight = (status: SourceStatus) => status === 'pending' || status === 'processing'

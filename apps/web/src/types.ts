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
  snippet: SnippetPart[]
}

export interface SearchResponse {
  query: string
  mode: 'keyword'
  semantic_available: boolean
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
}

export const isInFlight = (status: SourceStatus) => status === 'pending' || status === 'processing'

import type { Meta } from '../types'

export function makeMeta(overrides: { semantic?: boolean; chat?: boolean; message?: string | null } = {}): Meta {
  const { semantic = false, chat = false, message = null } = overrides
  return {
    status: 'ok',
    database: true,
    max_upload_bytes: 20 * 1024 * 1024,
    max_note_chars: 200_000,
    accepted_extensions: ['.markdown', '.md', '.pdf', '.txt'],
    capabilities: { keyword_search: true, semantic_search: semantic, grounded_chat: chat, memory_extraction: false },
    ai: {
      provider: semantic || chat ? 'ollama' : 'none',
      location: 'local',
      embedding_model: semantic ? 'embeddinggemma' : null,
      chat_model: chat ? 'qwen3.5:9b' : null,
      reachable: semantic || chat,
      message,
    },
    index: { ready_sources: 0, semantic_indexed: 0, semantic_pending: 0 },
  }
}

export function ndjsonResponse(events: unknown[]) {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      // Split mid-line to exercise buffering across chunks.
      const text = events.map((e) => JSON.stringify(e)).join('\n') + '\n'
      const mid = Math.floor(text.length / 2)
      controller.enqueue(encoder.encode(text.slice(0, mid)))
      controller.enqueue(encoder.encode(text.slice(mid)))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } })
}

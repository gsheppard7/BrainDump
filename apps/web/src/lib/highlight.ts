export interface TextPart {
  text: string
  highlight: boolean
}

const STOP_WORDS = new Set(['a', 'an', 'and', 'the', 'of', 'or', 'to', 'in', 'on', 'is', 'it', 'for'])

/** Extract plain terms from a web-search style query (drops quotes, operators, negations). */
export function queryTerms(query: string): string[] {
  return query
    .split(/\s+/)
    .filter((t) => t && !t.startsWith('-'))
    .map((t) => t.replace(/["()]/g, '').toLowerCase())
    .filter((t) => t.length > 1 && t !== 'or' && !STOP_WORDS.has(t))
}

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/**
 * Highlight words that start with a query term — a rough client-side approximation of
 * Postgres stemming (e.g. "restart" also marks "restarting").
 */
export function highlightTerms(text: string, terms: string[]): TextPart[] {
  if (!terms.length || !text) return text ? [{ text, highlight: false }] : []
  const pattern = new RegExp(`\\b(?:${terms.map(escapeRegExp).join('|')})\\w*`, 'giu')
  const parts: TextPart[] = []
  let last = 0
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0
    if (start > last) parts.push({ text: text.slice(last, start), highlight: false })
    parts.push({ text: match[0], highlight: true })
    last = start + match[0].length
  }
  if (last < text.length) parts.push({ text: text.slice(last), highlight: false })
  return parts
}

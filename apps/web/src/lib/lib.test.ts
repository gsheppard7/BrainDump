import { describe, expect, it } from 'vitest'

import { toApiError } from '../api'
import { citationNumber, linkCitations } from './citations'
import { precheckFile } from './files'
import { formatBytes } from './format'
import { highlightTerms, queryTerms } from './highlight'

const MB = 1024 * 1024
const file = (name: string, size: number) => {
  const f = new File(['x'], name)
  Object.defineProperty(f, 'size', { value: size })
  return f
}

describe('linkCitations', () => {
  it('links valid citation numbers and leaves others alone', () => {
    expect(linkCitations('See [1] and [2, 3] but not [7].', 3)).toBe(
      'See [\\[1\\]](#cite-1) and [\\[2\\]](#cite-2)[\\[3\\]](#cite-3) but not [7].',
    )
    expect(citationNumber('#cite-12')).toBe(12)
    expect(citationNumber('https://example.com')).toBeNull()
  })
})

describe('queryTerms', () => {
  it('drops operators, negations, quotes and stop words', () => {
    expect(queryTerms('"restart modem" -printer or the wifi')).toEqual(['restart', 'modem', 'wifi'])
  })
})

describe('highlightTerms', () => {
  it('marks words starting with a term, case-insensitively', () => {
    expect(highlightTerms('Restarting the modem fixes it', ['restart'])).toEqual([
      { text: 'Restarting', highlight: true },
      { text: ' the modem fixes it', highlight: false },
    ])
  })

  it('escapes regex characters and handles no terms', () => {
    expect(highlightTerms('a+b c', ['a+b'])[0]).toEqual({ text: 'a+b', highlight: true })
    expect(highlightTerms('plain', [])).toEqual([{ text: 'plain', highlight: false }])
  })
})

describe('precheckFile', () => {
  it('accepts supported files within the limit', () => {
    expect(precheckFile(file('notes.MD', 10), MB)).toBeNull()
  })

  it('rejects unsupported, empty and oversized files with clear messages', () => {
    expect(precheckFile(file('deck.pptx', 10), MB)).toMatch(/\.pptx files aren't supported/)
    expect(precheckFile(file('README', 10), MB)).toMatch(/without an extension/)
    expect(precheckFile(file('a.txt', 0), MB)).toBe('The file is empty.')
    expect(precheckFile(file('a.pdf', 3 * MB), MB)).toBe('File is 3.0 MB; the maximum upload size is 1.0 MB.')
  })
})

describe('formatBytes', () => {
  it('formats human sizes', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(20 * MB)).toBe('20 MB')
  })
})

describe('toApiError', () => {
  it('uses the API error envelope', () => {
    const err = toApiError(409, JSON.stringify({ error: { code: 'duplicate', message: 'Already there', details: { existing_source_id: 'abc' } } }))
    expect(err).toMatchObject({ status: 409, code: 'duplicate', message: 'Already there', details: { existing_source_id: 'abc' } })
  })

  it('falls back to friendly messages for non-JSON bodies', () => {
    expect(toApiError(413, '<html>Request Entity Too Large</html>').message).toBe('That file is too large to upload.')
    expect(toApiError(500, '').message).toBe('Request failed (500).')
  })
})

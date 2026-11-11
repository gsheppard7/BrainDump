import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeMeta } from '../test/fixtures'
import { jsonResponse, renderWithProviders } from '../test/render'
import type { SearchResponse, SourceList } from '../types'
import { LibraryPage } from './LibraryPage'

const emptyList: SourceList = { items: [], total: 0 }

const searchResponse: SearchResponse = {
  query: 'modem',
  mode: 'hybrid',
  semantic_available: true,
  notice: null,
  total: 1,
  query_has_terms: true,
  hits: [
    {
      source_id: 'src-1',
      title: 'Home Network Setup Guide',
      kind: 'file',
      file_type: 'pdf',
      created_at: new Date().toISOString(),
      chunk_id: 'chunk-1',
      chunk_ordinal: 2,
      page: 3,
      rank: 0.1,
      match_count: 1,
      match_reasons: ['keyword', 'semantic'],
      snippet: [
        { text: 'Restart order matters: ', highlight: false },
        { text: 'modem', highlight: true },
        { text: ' first.', highlight: false },
      ],
    },
  ],
}

describe('LibraryPage', () => {
  it('searches as you type and links to the matching passage', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.startsWith('/api/search')) return jsonResponse(searchResponse)
      if (url.startsWith('/api/meta')) return jsonResponse(makeMeta({ semantic: true }))
      return jsonResponse(emptyList)
    })
    renderWithProviders(<LibraryPage />, { route: '/library' })

    expect(await screen.findByText(/Your library is empty/)).toBeInTheDocument()
    expect(await screen.findByText('Hybrid search')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Search your library'), 'modem')

    const mark = await screen.findByText('modem', { selector: 'mark' })
    expect(mark).toBeInTheDocument()
    expect(screen.getByText(/p\. 3/)).toBeInTheDocument()
    expect(screen.getByText('meaning')).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /Home Network Setup Guide/ })
    expect(link).toHaveAttribute('href', '/sources/src-1?q=modem&chunk=2')

    const searchCalls = fetchMock.mock.calls.filter(([u]) => String(u).startsWith('/api/search'))
    expect(searchCalls).toHaveLength(1)
  })

  it('shows API errors to the user', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ error: { code: 'internal', message: 'Database unavailable', details: {} } }, 503),
    )
    renderWithProviders(<LibraryPage />, { route: '/library' })
    expect((await screen.findAllByRole('alert'))[0]).toHaveTextContent('Database unavailable')
  })
})

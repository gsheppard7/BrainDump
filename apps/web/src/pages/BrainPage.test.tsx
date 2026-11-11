import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { makeMeta } from '../test/fixtures'
import { jsonResponse, renderWithProviders } from '../test/render'
import { BrainPage } from './BrainPage'

describe('BrainPage', () => {
  it('renders graph stats and empty guidance when there are no sources', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.startsWith('/api/meta')) return jsonResponse(makeMeta({ semantic: true }))
      if (url.startsWith('/api/graph')) {
        return jsonResponse({
          nodes: [],
          edges: [],
          stats: { sources: 0, connections: 0, indexed: 0, pending: 0, min_similarity: 0.3 },
        })
      }
      throw new Error(`unexpected ${url}`)
    })
    renderWithProviders(<BrainPage />, { route: '/brain' })
    expect(await screen.findByText(/Nothing to map yet/)).toBeInTheDocument()
  })

  it('shows source count when the graph has nodes', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input)
      if (url.startsWith('/api/meta')) return jsonResponse(makeMeta({ semantic: true }))
      if (url.startsWith('/api/graph')) {
        return jsonResponse({
          nodes: [
            {
              id: 'a',
              title: 'Career notes',
              kind: 'note',
              file_type: null,
              char_count: 1200,
              chunk_count: 2,
              created_at: new Date().toISOString(),
              embedding_status: 'done',
            },
            {
              id: 'b',
              title: 'Projects',
              kind: 'file',
              file_type: 'markdown',
              char_count: 4000,
              chunk_count: 5,
              created_at: new Date().toISOString(),
              embedding_status: 'done',
            },
          ],
          edges: [{ source: 'a', target: 'b', weight: 0.62 }],
          stats: { sources: 2, connections: 1, indexed: 2, pending: 0, min_similarity: 0.3 },
        })
      }
      throw new Error(`unexpected ${url}`)
    })
    renderWithProviders(<BrainPage />, { route: '/brain' })
    expect(await screen.findByText('Sources')).toBeInTheDocument()
    expect(screen.getByText('Connections')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Knowledge graph/ })).toBeInTheDocument()
    expect(screen.getByText(/How to read this/)).toBeInTheDocument()
  })
})

import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { makeMeta, ndjsonResponse } from '../test/fixtures'
import { jsonResponse, renderWithProviders } from '../test/render'
import type { AskPassage } from '../types'
import { AskPage } from './AskPage'

const passage = (n: number, title: string): AskPassage => ({
  n,
  source_id: `src-${n}`,
  chunk_id: `chunk-${n}`,
  chunk_ordinal: 0,
  page: n === 1 ? 3 : null,
  title,
  kind: 'file',
  file_type: 'pdf',
  created_at: new Date().toISOString(),
  excerpt: `${title} excerpt`,
  match_reasons: ['semantic'],
})

describe('AskPage', () => {
  it('streams a cited answer and links citations to sources', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      if (String(input).startsWith('/api/meta')) return jsonResponse(makeMeta({ semantic: true, chat: true }))
      return ndjsonResponse([
        { type: 'meta', model: 'qwen3.5:9b', location: 'local', notice: null },
        { type: 'context', passages: [passage(1, 'Network Guide'), passage(2, 'Groceries')] },
        { type: 'delta', text: 'Restart the **modem** first [1]' },
        { type: 'delta', text: ', then the router [1, 9]. ![x](https://evil.example/p.png)' },
        { type: 'done', citations: [1], grounded: true },
      ])
    })
    renderWithProviders(<AskPage />, { route: '/ask' })

    await userEvent.click(screen.getByRole('radio', { name: 'Plan' }))
    await userEvent.type(screen.getByLabelText('Your question'), 'How do I restart the network?')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    const answer = await screen.findByRole('region', { name: 'Answer' })
    expect(await within(answer).findByText('modem')).toBeInTheDocument()
    expect(within(answer).getByText(/Cites 1 source passage/)).toBeInTheDocument()

    const citations = within(answer).getAllByRole('link', { name: '1' })
    expect(citations[0]).toHaveAttribute('href', '/sources/src-1?q=How+do+I+restart+the+network%3F&chunk=0')
    expect(within(answer).queryByRole('link', { name: '9' })).toBeNull()
    expect(answer.querySelector('img')).toBeNull()

    expect(within(answer).getByText('not cited')).toBeInTheDocument()

    const askCall = fetchMock.mock.calls.find(([u]) => String(u) === '/api/ask')!
    expect(JSON.parse(String(askCall[1]!.body))).toEqual({ question: 'How do I restart the network?', mode: 'plan' })
  })

  it('explains when local AI is unavailable', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse(makeMeta({ message: "Ollama isn't running. Start it with: brew services start ollama" })),
    )
    renderWithProviders(<AskPage />, { route: '/ask' })
    expect(await screen.findByText(/brew services start ollama/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })
})

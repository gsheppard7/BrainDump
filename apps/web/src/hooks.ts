import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import { api, type ListParams } from './api'
import { isInFlight } from './types'

const POLL_MS = 1000

export function useMeta() {
  return useQuery({ queryKey: ['meta'], queryFn: api.meta, staleTime: 60_000 })
}

export function useSources(params: ListParams = {}) {
  return useQuery({
    queryKey: ['sources', 'list', params],
    queryFn: () => api.listSources(params),
    refetchInterval: (query) =>
      query.state.data?.items.some((s) => isInFlight(s.status)) ? POLL_MS : false,
  })
}

export function useSource(id: string) {
  return useQuery({
    queryKey: ['sources', 'detail', id],
    queryFn: () => api.getSource(id),
    refetchInterval: (query) => (query.state.data && isInFlight(query.state.data.status) ? POLL_MS : false),
  })
}

export function useSearch(q: string) {
  const query = q.trim()
  return useQuery({
    queryKey: ['search', query],
    queryFn: () => api.search(query),
    enabled: query.length > 0,
    placeholderData: (prev) => prev,
  })
}

export function useInvalidateSources() {
  const client = useQueryClient()
  return () => Promise.all([
    client.invalidateQueries({ queryKey: ['sources'] }),
    client.invalidateQueries({ queryKey: ['search'] }),
  ])
}

export function useCreateNote() {
  const invalidate = useInvalidateSources()
  return useMutation({
    mutationFn: ({ body, title }: { body: string; title?: string }) => api.createNote(body, title),
    onSuccess: invalidate,
  })
}

export function useDeleteSource() {
  const invalidate = useInvalidateSources()
  return useMutation({ mutationFn: api.deleteSource, onSuccess: invalidate })
}

export function useRetrySource() {
  const invalidate = useInvalidateSources()
  return useMutation({ mutationFn: api.retrySource, onSuccess: invalidate })
}

export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}

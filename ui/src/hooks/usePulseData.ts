import { useState, useEffect, useCallback, useRef } from 'react'
import { apiClient } from '@/lib/api'
import type {
  PulseOverview,
  PulseQueryParams,
  PulsePaginatedResponse,
  PulseRepo,
  PulseCommit,
  PulsePromptDetail,
  PulsePerson,
} from '@/types/pulse'

interface UseDataResult<T> {
  data: T | null
  isLoading: boolean
  error: string | null
  refetch: () => void
}

/**
 * Generic fetch hook shared by all Pulse data hooks.
 *
 * - 150ms debounce: batches rapid filter/sort clicks into one server request
 * - AbortController: cancels in-flight requests when deps change or on unmount
 * - Aborted requests silently ignored (not surfaced as errors)
 */
function usePulseQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  label: string
): UseDataResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const abortRef = useRef<AbortController | null>(null)

  const fetchData = useCallback(async () => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsLoading(true)
    setError(null)
    try {
      const result = await fetcherRef.current(controller.signal)
      setData(result)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof Error ? err.message : `Failed to fetch ${label}`)
    } finally {
      if (!controller.signal.aborted) {
        setIsLoading(false)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    const timer = setTimeout(() => { fetchData() }, 150)
    return () => {
      clearTimeout(timer)
      abortRef.current?.abort()
    }
  }, [fetchData])

  return { data, isLoading, error, refetch: fetchData }
}

export function usePulseOverview(days: number | null = 30): UseDataResult<PulseOverview> {
  return usePulseQuery(
    (signal) => apiClient.getPulseOverview(days, signal),
    [days],
    'overview'
  )
}

export function usePulseRepos(params: PulseQueryParams = {}): UseDataResult<PulsePaginatedResponse<PulseRepo>> {
  return usePulseQuery(
    (signal) => apiClient.getPulseRepos(params, signal),
    [params.days, params.sort, params.limit, params.offset],
    'repos'
  )
}

export function usePulseCommits(params: PulseQueryParams = {}): UseDataResult<PulsePaginatedResponse<PulseCommit>> {
  return usePulseQuery(
    (signal) => apiClient.getPulseCommits(params, signal),
    [params.days, params.sort, params.repo, params.limit, params.offset],
    'commits'
  )
}

export function usePulsePrompts(params: PulseQueryParams = {}): UseDataResult<PulsePaginatedResponse<PulsePromptDetail>> {
  return usePulseQuery(
    (signal) => apiClient.getPulsePrompts(params, signal),
    [params.days, params.sort, params.repo, params.email, params.limit, params.offset],
    'prompts'
  )
}

export function usePulsePeople(params: PulseQueryParams = {}): UseDataResult<PulsePaginatedResponse<PulsePerson>> {
  return usePulseQuery(
    (signal) => apiClient.getPulsePeople(params, signal),
    [params.days, params.sort, params.repo, params.limit, params.offset],
    'people'
  )
}

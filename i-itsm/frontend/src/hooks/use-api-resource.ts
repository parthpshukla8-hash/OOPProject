import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../api/api-client'
import type { Params } from '../api/api-client'

interface ResourceState<T> {
  data: T | null
  error: ApiError | null
  isLoading: boolean
  reload: () => void
}

/** Loads a GET resource. Pass path = null to skip. Re-fetches when path/params change or every refreshMs. */
export function useApiResource<T>(path: string | null, params?: Params, refreshMs?: number): ResourceState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [isLoading, setIsLoading] = useState(path !== null)
  const [version, setVersion] = useState(0)
  const hasLoaded = useRef(false)
  const paramsKey = JSON.stringify(params ?? {})

  useEffect(() => {
    if (path === null) { setData(null); setIsLoading(false); return }
    let cancelled = false
    if (!hasLoaded.current) setIsLoading(true)
    api.get<T>(path, JSON.parse(paramsKey) as Params)
      .then((result) => { if (!cancelled) { setData(result); setError(null) } })
      .catch((failure: ApiError) => { if (!cancelled) setError(failure) })
      .finally(() => { if (!cancelled) { setIsLoading(false); hasLoaded.current = true } })
    return () => { cancelled = true }
  }, [path, paramsKey, version])

  useEffect(() => {
    if (!refreshMs || path === null) return undefined
    const timer = window.setInterval(() => setVersion((current) => current + 1), refreshMs)
    return () => window.clearInterval(timer)
  }, [refreshMs, path])

  useEffect(() => { hasLoaded.current = false }, [path])

  const reload = useCallback(() => setVersion((current) => current + 1), [])
  return { data, error, isLoading, reload }
}

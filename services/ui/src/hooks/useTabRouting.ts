import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Tab state synced to a URL search param with validation.
 *
 * Reads the active tab from `?{param}=`, falling back to `defaultTab` when
 * the param is missing or not one of `tabs`. Setting a tab updates the URL
 * (pushing a history entry so back/forward moves between tabs) while
 * preserving all unrelated search params.
 */
export function useTabRouting<T extends string>(
  tabs: readonly T[],
  defaultTab: T,
  param = 'tab',
): [T, (tab: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams()

  const raw = searchParams.get(param)
  const active: T = raw !== null && (tabs as readonly string[]).includes(raw) ? (raw as T) : defaultTab

  const setTab = useCallback(
    (tab: T) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set(param, tab)
        return next
      })
    },
    [param, setSearchParams],
  )

  return [active, setTab]
}

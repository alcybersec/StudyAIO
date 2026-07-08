import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

interface TabRoutingOptions<T extends string> {
  /**
   * Params scoped to a specific tab: `{ exam: 'exams' }` removes `?exam=`
   * whenever a tab other than `exams` is selected.
   */
  clearParams?: Record<string, T>
}

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
  options: TabRoutingOptions<T> = {},
): [T, (tab: T) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const { clearParams } = options

  const raw = searchParams.get(param)
  const active: T = raw !== null && (tabs as readonly string[]).includes(raw) ? (raw as T) : defaultTab

  const setTab = useCallback(
    (tab: T) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set(param, tab)
        if (clearParams) {
          for (const [name, owningTab] of Object.entries(clearParams)) {
            if (tab !== owningTab) next.delete(name)
          }
        }
        return next
      })
    },
    [param, setSearchParams, clearParams],
  )

  return [active, setTab]
}

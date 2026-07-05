export type WidgetState = 'loading' | 'error' | 'empty' | 'data'

export interface WidgetStateInput {
  isLoading: boolean
  isError: boolean
  /** Query has resolved data (including cached data while offline or refetching). */
  hasData: boolean
  /** The resolved data is present but has nothing to show. */
  isEmpty: boolean
}

/**
 * Pick which of the four widget states to render.
 *
 * Cached data always wins: if a background refetch fails or the client is
 * offline, the widget keeps rendering the last known data instead of
 * collapsing into an error state.
 */
export function selectWidgetState({ isLoading, isError, hasData, isEmpty }: WidgetStateInput): WidgetState {
  if (hasData) return isEmpty ? 'empty' : 'data'
  if (isError) return 'error'
  if (isLoading) return 'loading'
  return 'empty'
}

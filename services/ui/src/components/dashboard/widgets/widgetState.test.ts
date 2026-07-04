import { describe, expect, it } from 'vitest'
import { selectWidgetState } from './widgetState'

describe('selectWidgetState', () => {
  it('returns loading during first fetch with no data', () => {
    expect(selectWidgetState({ isLoading: true, isError: false, hasData: false, isEmpty: true })).toBe('loading')
  })

  it('returns error when the query failed with no cached data', () => {
    expect(selectWidgetState({ isLoading: false, isError: true, hasData: false, isEmpty: true })).toBe('error')
  })

  it('returns data when data is present and non-empty', () => {
    expect(selectWidgetState({ isLoading: false, isError: false, hasData: true, isEmpty: false })).toBe('data')
  })

  it('returns empty when data resolved but has nothing to show', () => {
    expect(selectWidgetState({ isLoading: false, isError: false, hasData: true, isEmpty: true })).toBe('empty')
  })

  it('prefers cached data over a background refetch error (offline)', () => {
    expect(selectWidgetState({ isLoading: false, isError: true, hasData: true, isEmpty: false })).toBe('data')
  })

  it('prefers cached data over loading during a background refetch', () => {
    expect(selectWidgetState({ isLoading: true, isError: false, hasData: true, isEmpty: false })).toBe('data')
  })

  it('falls back to empty when idle with no data (paused query)', () => {
    expect(selectWidgetState({ isLoading: false, isError: false, hasData: false, isEmpty: true })).toBe('empty')
  })
})

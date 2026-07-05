import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useDebouncedValue } from './useDebouncedValue'

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebouncedValue('asl', 200))
    expect(result.current).toBe('asl')
  })

  it('does not update until the delay has elapsed', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 200), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'as' })
    act(() => {
      vi.advanceTimersByTime(199)
    })
    expect(result.current).toBe('a')
    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current).toBe('as')
  })

  it('restarts the timer on every change (only the last value lands)', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 200), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'as' })
    act(() => {
      vi.advanceTimersByTime(150)
    })
    rerender({ value: 'asl' })
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(result.current).toBe('a')
    act(() => {
      vi.advanceTimersByTime(50)
    })
    expect(result.current).toBe('asl')
  })
})

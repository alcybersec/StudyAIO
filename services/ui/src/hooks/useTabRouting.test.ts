import { describe, expect, it } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { MemoryRouter, useNavigate, useSearchParams } from 'react-router-dom'
import { useTabRouting } from './useTabRouting'

const TABS = ['flashcards', 'timed', 'exams', 'history'] as const

function wrapperWith(initialEntries: string[]) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(MemoryRouter, { initialEntries }, children)
  }
}

describe('useTabRouting', () => {
  it('returns the default tab when no param is present', () => {
    const { result } = renderHook(() => useTabRouting(TABS, 'flashcards'), {
      wrapper: wrapperWith(['/study']),
    })
    expect(result.current[0]).toBe('flashcards')
  })

  it('reads the active tab from the ?tab= param', () => {
    const { result } = renderHook(() => useTabRouting(TABS, 'flashcards'), {
      wrapper: wrapperWith(['/study?tab=exams']),
    })
    expect(result.current[0]).toBe('exams')
  })

  it('falls back to the default tab for an invalid param value', () => {
    const { result } = renderHook(() => useTabRouting(TABS, 'flashcards'), {
      wrapper: wrapperWith(['/study?tab=bogus']),
    })
    expect(result.current[0]).toBe('flashcards')
  })

  it('setTab syncs the ?tab= param', () => {
    const { result } = renderHook(
      () => {
        const tab = useTabRouting(TABS, 'flashcards')
        const [params] = useSearchParams()
        return { tab, params }
      },
      { wrapper: wrapperWith(['/study']) },
    )
    act(() => result.current.tab[1]('timed'))
    expect(result.current.tab[0]).toBe('timed')
    expect(result.current.params.get('tab')).toBe('timed')
  })

  it('preserves unrelated params when switching tabs', () => {
    const { result } = renderHook(
      () => {
        const tab = useTabRouting(TABS, 'flashcards')
        const [params] = useSearchParams()
        return { tab, params }
      },
      { wrapper: wrapperWith(['/study?tab=exams&exam=abc123']) },
    )
    act(() => result.current.tab[1]('history'))
    expect(result.current.tab[0]).toBe('history')
    expect(result.current.params.get('exam')).toBe('abc123')
  })

  it('supports a custom param name', () => {
    const { result } = renderHook(() => useTabRouting(TABS, 'flashcards', 'view'), {
      wrapper: wrapperWith(['/study?view=timed']),
    })
    expect(result.current[0]).toBe('timed')
  })

  it('clears listed params when switching to a tab they are not scoped to', () => {
    const { result } = renderHook(
      () => {
        const tab = useTabRouting(TABS, 'flashcards', 'tab', { clearParams: { exam: 'exams' } })
        const [params] = useSearchParams()
        return { tab, params }
      },
      { wrapper: wrapperWith(['/study?tab=exams&exam=abc123']) },
    )
    act(() => result.current.tab[1]('history'))
    expect(result.current.tab[0]).toBe('history')
    expect(result.current.params.get('exam')).toBeNull()
  })

  it('keeps scoped params when switching to their owning tab', () => {
    const { result } = renderHook(
      () => {
        const tab = useTabRouting(TABS, 'flashcards', 'tab', { clearParams: { exam: 'exams' } })
        const [params] = useSearchParams()
        return { tab, params }
      },
      { wrapper: wrapperWith(['/study?tab=history&exam=abc123']) },
    )
    act(() => result.current.tab[1]('exams'))
    expect(result.current.params.get('exam')).toBe('abc123')
  })

  it('works with history back/forward navigation', () => {
    const { result } = renderHook(
      () => {
        const tab = useTabRouting(TABS, 'flashcards')
        const navigate = useNavigate()
        return { tab, navigate }
      },
      { wrapper: wrapperWith(['/study']) },
    )
    act(() => result.current.tab[1]('timed'))
    expect(result.current.tab[0]).toBe('timed')
    act(() => result.current.tab[1]('exams'))
    expect(result.current.tab[0]).toBe('exams')
    act(() => result.current.navigate(-1))
    expect(result.current.tab[0]).toBe('timed')
    act(() => result.current.navigate(1))
    expect(result.current.tab[0]).toBe('exams')
  })
})

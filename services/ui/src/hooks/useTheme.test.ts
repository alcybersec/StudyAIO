import { describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

interface MediaQueryListMock {
  matches: boolean
  media: string
  addEventListener: ReturnType<typeof vi.fn>
  removeEventListener: ReturnType<typeof vi.fn>
}

async function loadUseTheme(mql: MediaQueryListMock) {
  vi.resetModules()
  window.matchMedia = vi.fn().mockReturnValue(mql) as unknown as typeof window.matchMedia
  const mod = await import('./useTheme')
  return mod.useTheme
}

function makeMql(): MediaQueryListMock {
  return {
    matches: false,
    media: '(prefers-color-scheme: dark)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }
}

describe('useTheme media-query listener lifecycle', () => {
  it('registers the OS listener on first subscribe, not at module load', async () => {
    const mql = makeMql()
    const useTheme = await loadUseTheme(mql)
    expect(mql.addEventListener).not.toHaveBeenCalled()

    const { unmount } = renderHook(() => useTheme())
    expect(mql.addEventListener).toHaveBeenCalledTimes(1)
    unmount()
  })

  it('removes the same handler on last unsubscribe (symmetry)', async () => {
    const mql = makeMql()
    const useTheme = await loadUseTheme(mql)

    const { unmount } = renderHook(() => useTheme())
    expect(mql.removeEventListener).not.toHaveBeenCalled()

    unmount()
    expect(mql.removeEventListener).toHaveBeenCalledTimes(1)
    const added = mql.addEventListener.mock.calls[0]
    const removed = mql.removeEventListener.mock.calls[0]
    expect(removed[0]).toBe(added[0])
    expect(removed[1]).toBe(added[1])
  })

  it('keeps a single OS listener across multiple subscribers', async () => {
    const mql = makeMql()
    const useTheme = await loadUseTheme(mql)

    const first = renderHook(() => useTheme())
    const second = renderHook(() => useTheme())
    expect(mql.addEventListener).toHaveBeenCalledTimes(1)

    first.unmount()
    expect(mql.removeEventListener).not.toHaveBeenCalled()

    second.unmount()
    expect(mql.removeEventListener).toHaveBeenCalledTimes(1)
  })
})

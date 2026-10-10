import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { usePipelineEvents } from './usePipelineEvents'

type Listener = (e: MessageEvent) => void

class FakeEventSource {
  static last: FakeEventSource | null = null
  listeners: Record<string, Listener> = {}
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  constructor() {
    FakeEventSource.last = this
  }
  addEventListener(name: string, fn: Listener) {
    this.listeners[name] = fn
  }
  close() {}
}

describe('usePipelineEvents malformed frames', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('skips a malformed frame and still handles the next one', () => {
    vi.stubGlobal('EventSource', FakeEventSource)
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { result } = renderHook(() => usePipelineEvents())
    const es = FakeEventSource.last!
    act(() => {
      es.listeners.pipeline({ data: '{oops' } as MessageEvent)
    })
    expect(result.current.events).toHaveLength(0)
    act(() => {
      es.listeners.pipeline({ data: JSON.stringify({ artifact_id: 'a1', stage: 'extract' }) } as MessageEvent)
    })
    expect(result.current.events).toHaveLength(1)
    spy.mockRestore()
  })
})

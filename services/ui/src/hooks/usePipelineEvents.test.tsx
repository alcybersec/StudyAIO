import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { usePipelineEvents } from './usePipelineEvents'

type Listener = (event: MessageEvent) => void

class FakeEventSource {
  static instances: FakeEventSource[] = []
  url: string
  closed = false
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  private listeners = new Map<string, Set<Listener>>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(type: string, cb: Listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(cb)
  }

  removeEventListener(type: string, cb: Listener) {
    this.listeners.get(type)?.delete(cb)
  }

  close() {
    this.closed = true
  }

  emit(type: string, data: string) {
    for (const cb of this.listeners.get(type) ?? []) {
      cb({ data } as MessageEvent)
    }
  }

  open() {
    this.onopen?.()
  }

  fail() {
    this.onerror?.()
  }
}

function lastSource(): FakeEventSource {
  return FakeEventSource.instances[FakeEventSource.instances.length - 1]
}

const pipelineEvent = (i: number) =>
  JSON.stringify({ artifact_id: 'a1', stage: 'extract', status: 'running', seq: i })

describe('usePipelineEvents', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeEventSource.instances = []
    vi.stubGlobal('EventSource', FakeEventSource)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('collects pipeline events and reports open connection state', () => {
    const { result } = renderHook(() => usePipelineEvents(['a1']))
    act(() => {
      lastSource().open()
      lastSource().emit('pipeline', pipelineEvent(1))
    })
    expect(result.current.connectionState).toBe('open')
    expect(result.current.connected).toBe(true)
    expect(result.current.events).toHaveLength(1)
  })

  it('caps the event buffer at 200', () => {
    const { result } = renderHook(() => usePipelineEvents(['a1']))
    act(() => {
      lastSource().open()
      for (let i = 0; i < 250; i++) {
        lastSource().emit('pipeline', pipelineEvent(i))
      }
    })
    expect(result.current.events).toHaveLength(200)
    // Oldest events dropped, newest kept
    expect((result.current.events[199] as { seq?: number }).seq).toBe(249)
  })

  it('reconnects with backoff after an error', () => {
    const { result } = renderHook(() => usePipelineEvents(['a1']))
    const first = lastSource()
    act(() => {
      first.open()
      first.fail()
    })
    expect(result.current.connectionState).toBe('reconnecting')
    expect(result.current.connected).toBe(false)
    expect(first.closed).toBe(true)
    expect(FakeEventSource.instances).toHaveLength(1)

    act(() => {
      vi.advanceTimersByTime(1_000)
    })
    expect(FakeEventSource.instances).toHaveLength(2)

    act(() => {
      lastSource().open()
    })
    expect(result.current.connectionState).toBe('open')
  })

  it('closes the source on unmount', () => {
    const { unmount } = renderHook(() => usePipelineEvents(['a1']))
    const source = lastSource()
    unmount()
    expect(source.closed).toBe(true)
  })
})

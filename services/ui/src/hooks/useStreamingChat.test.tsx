import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { chatApi } from '../api/endpoints'
import { useStreamingChat } from './useStreamingChat'

vi.mock('../api/endpoints', () => ({
  chatApi: {
    streamMessage: vi.fn(),
  },
}))

const streamMessage = vi.mocked(chatApi.streamMessage)

function sseResponse(events: string): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(events))
      controller.close()
    },
  })
  return new Response(body, { status: 200 })
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('useStreamingChat', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('accumulates tokens from a successful stream', async () => {
    streamMessage.mockResolvedValue(
      sseResponse('event: token\ndata: Hel\n\nevent: token\ndata: lo\n\n'),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.streamingText).toBe('Hello')
    expect(result.current.connectionState).toBe('idle')
    expect(result.current.error).toBeNull()
  })

  it('marks the stream interrupted and auto-retries up to 3 times with backoff', async () => {
    vi.useFakeTimers()
    streamMessage.mockRejectedValue(new TypeError('Failed to fetch'))
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })

    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.connectionState).toBe('interrupted')
    expect(streamMessage).toHaveBeenCalledTimes(1)

    // Backoff: 1s, 2s, 4s
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000)
    })
    expect(streamMessage).toHaveBeenCalledTimes(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000)
    })
    expect(streamMessage).toHaveBeenCalledTimes(3)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000)
    })
    expect(streamMessage).toHaveBeenCalledTimes(4)

    // Retries exhausted
    expect(result.current.connectionState).toBe('error')
    expect(result.current.error).not.toBeNull()
  })

  it('recovers when a retry succeeds', async () => {
    vi.useFakeTimers()
    streamMessage
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValue(sseResponse('event: token\ndata: ok\n\n'))
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })

    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.connectionState).toBe('interrupted')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000)
    })
    vi.useRealTimers()
    await waitFor(() => expect(result.current.connectionState).toBe('idle'))
    expect(result.current.streamingText).toBe('ok')
  })

  it('exposes resume() to manually retry after retries are exhausted', async () => {
    vi.useFakeTimers()
    streamMessage.mockRejectedValue(new TypeError('Failed to fetch'))
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })

    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(result.current.connectionState).toBe('error')

    streamMessage.mockResolvedValue(sseResponse('event: token\ndata: back\n\n'))
    await act(async () => {
      await result.current.resume()
    })
    expect(result.current.connectionState).toBe('idle')
    expect(result.current.streamingText).toBe('back')
  })

  it('does not retry when the server rejects the request', async () => {
    streamMessage.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Session not found' }), { status: 404 }),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.connectionState).toBe('error')
    expect(streamMessage).toHaveBeenCalledTimes(1)
  })

  it('captures the quiz-builder action from the done event', async () => {
    const done = JSON.stringify({
      content: 'ok',
      action: { type: 'open_quiz_builder', course_code: 'CSCI369', course_id: 'c1', week: 2 },
    })
    streamMessage.mockResolvedValue(
      sseResponse(`event: token\ndata: ok\n\nevent: done\ndata: ${done}\n\n`),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('make a test')
    })
    expect(result.current.action).toEqual({
      type: 'open_quiz_builder',
      course_code: 'CSCI369',
      course_id: 'c1',
      week: 2,
    })
  })

  it('leaves action null when done carries none', async () => {
    streamMessage.mockResolvedValue(
      sseResponse(`event: done\ndata: ${JSON.stringify({ content: 'ok', action: null })}\n\n`),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.action).toBeNull()
  })

  it('survives a malformed done frame and keeps the streamed tokens', async () => {
    streamMessage.mockResolvedValue(
      sseResponse('event: token\ndata: Hi\n\nevent: done\ndata: {not json\n\nevent: token\ndata: !\n\n'),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.streamingText).toBe('Hi!')
    expect(result.current.connectionState).toBe('idle')
    expect(result.current.error).toBeNull()
  })

  it('shows a friendly message, not the server detail, on a rejected request', async () => {
    streamMessage.mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Traceback: KeyError session' }), { status: 500 }),
    )
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    expect(result.current.error).toBe('The server hit a problem')
    expect(result.current.error).not.toContain('Traceback')
  })

  it('does not surface the raw payload of an SSE error event', async () => {
    vi.useFakeTimers()
    streamMessage.mockResolvedValue(sseResponse('event: error\ndata: ValueError: secret internals\n\n'))
    const { result } = renderHook(() => useStreamingChat('s1'), { wrapper })
    await act(async () => {
      await result.current.sendStreaming('hi')
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(result.current.connectionState).toBe('error')
    expect(result.current.error).toBe('Streaming failed')
  })
})

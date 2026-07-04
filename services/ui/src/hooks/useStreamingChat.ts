import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { chatApi } from '../api/endpoints'
import type { MessageScope } from '../types'

export type ChatConnectionState = 'idle' | 'streaming' | 'interrupted' | 'error'

interface StreamingState {
  isStreaming: boolean
  streamingText: string
  error: string | null
  connectionState: ChatConnectionState
  /** 1-based attempt number while auto-retrying, 0 otherwise. */
  retryAttempt: number
}

const MAX_AUTO_RETRIES = 3
const BASE_BACKOFF_MS = 1_000

export function useStreamingChat(sessionId: string) {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    streamingText: '',
    error: null,
    connectionState: 'idle',
    retryAttempt: 0,
  })
  const abortRef = useRef<AbortController | null>(null)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastContentRef = useRef<string | null>(null)
  const lastScopeRef = useRef<MessageScope | undefined>(undefined)
  const queryClient = useQueryClient()

  useEffect(
    () => () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      abortRef.current?.abort()
    },
    [],
  )

  const invalidateMessages = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['chat', 'messages', sessionId] })
    queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
  }, [queryClient, sessionId])

  const runStream = useCallback(
    async (content: string, scope: MessageScope | undefined, attempt: number): Promise<void> => {
      setState((s) => ({
        ...s,
        isStreaming: true,
        streamingText: attempt === 0 ? '' : s.streamingText,
        error: null,
        connectionState: 'streaming',
        retryAttempt: attempt,
      }))

      abortRef.current = new AbortController()

      try {
        const response = await chatApi.streamMessage(sessionId, content, scope)

        if (!response.ok) {
          // The server rejected the request — retrying won't change that
          const body = await response.json().catch(() => ({ detail: response.statusText }))
          setState((s) => ({
            ...s,
            isStreaming: false,
            error: body.detail || 'Stream request failed',
            connectionState: 'error',
          }))
          return
        }

        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''
        let accumulated = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Parse SSE events from buffer
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          let eventType = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              const data = line.slice(6)

              if (eventType === 'token') {
                accumulated += data
                setState((s) => ({ ...s, streamingText: accumulated }))
              } else if (eventType === 'done') {
                try {
                  const parsed = JSON.parse(data)
                  // Use the final parsed content (may differ from raw tokens if JSON was parsed)
                  if (parsed.content) {
                    accumulated = parsed.content
                    setState((s) => ({ ...s, streamingText: accumulated }))
                  }
                } catch {
                  // Ignore parse errors
                }
              } else if (eventType === 'error') {
                throw new Error(data)
              }
            }
          }
        }

        // Invalidate cache to pick up the saved messages
        invalidateMessages()
        setState((s) => ({
          ...s,
          isStreaming: false,
          error: null,
          connectionState: 'idle',
          retryAttempt: 0,
        }))
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          setState((s) => ({ ...s, isStreaming: false, connectionState: 'idle', retryAttempt: 0 }))
          return
        }

        // The stream dropped mid-flight (network/proxy). Refresh whatever the
        // server persisted so far, then auto-retry with backoff.
        invalidateMessages()

        if (attempt < MAX_AUTO_RETRIES) {
          setState((s) => ({
            ...s,
            isStreaming: true,
            connectionState: 'interrupted',
            retryAttempt: attempt + 1,
          }))
          retryTimerRef.current = setTimeout(() => {
            retryTimerRef.current = null
            void runStream(content, scope, attempt + 1)
          }, BASE_BACKOFF_MS * 2 ** attempt)
          return
        }

        setState((s) => ({
          ...s,
          isStreaming: false,
          error: (err as Error).message || 'Streaming failed',
          connectionState: 'error',
        }))
      } finally {
        abortRef.current = null
      }
    },
    [sessionId, invalidateMessages],
  )

  const sendStreaming = useCallback(
    async (content: string, scope?: MessageScope) => {
      lastContentRef.current = content
      lastScopeRef.current = scope
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      await runStream(content, scope, 0)
    },
    [runStream],
  )

  /** Manually retry the interrupted stream (after auto-retries are exhausted). */
  const resume = useCallback(async () => {
    if (!lastContentRef.current) return
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    await runStream(lastContentRef.current, lastScopeRef.current, 0)
  }, [runStream])

  const abort = useCallback(() => {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
    abortRef.current?.abort()
  }, [])

  return {
    ...state,
    sendStreaming,
    resume,
    abort,
  }
}

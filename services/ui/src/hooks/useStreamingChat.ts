import { useCallback, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { chatApi } from '../api/endpoints'
import type { MessageScope } from '../types'

interface StreamingState {
  isStreaming: boolean
  streamingText: string
  error: string | null
}

export function useStreamingChat(sessionId: string) {
  const [state, setState] = useState<StreamingState>({
    isStreaming: false,
    streamingText: '',
    error: null,
  })
  const abortRef = useRef<AbortController | null>(null)
  const queryClient = useQueryClient()

  const sendStreaming = useCallback(
    async (content: string, scope?: MessageScope) => {
      setState({ isStreaming: true, streamingText: '', error: null })

      abortRef.current = new AbortController()

      try {
        const response = await chatApi.streamMessage(sessionId, content, scope)

        if (!response.ok) {
          const body = await response.json().catch(() => ({ detail: response.statusText }))
          throw new Error(body.detail || 'Stream request failed')
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
        queryClient.invalidateQueries({ queryKey: ['chat', 'messages', sessionId] })
        queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          setState((s) => ({
            ...s,
            error: (err as Error).message || 'Streaming failed',
          }))
        }
      } finally {
        setState((s) => ({ ...s, isStreaming: false }))
        abortRef.current = null
      }
    },
    [sessionId, queryClient],
  )

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return {
    ...state,
    sendStreaming,
    abort,
  }
}

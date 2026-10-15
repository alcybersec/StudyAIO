import { useEffect, useMemo, useRef, useState } from 'react'
import { logRawError } from '../lib/userError'
import type { PipelineEvent } from '../types'

export type PipelineConnectionState = 'connecting' | 'open' | 'reconnecting'

// Keep memory bounded on long pipeline sessions
const MAX_EVENTS = 200
const MIN_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 30_000

/**
 * Low-level SSE subscription. Do not call this from pages: the app shell owns
 * the single connection via PipelineEventsProvider (use usePipelineProgress).
 * `onEvent` fires for every well-formed, matching frame.
 */
export function usePipelineEvents(artifactIds?: string[], onEvent?: (event: PipelineEvent) => void) {
  const onEventRef = useRef(onEvent)
  useEffect(() => {
    onEventRef.current = onEvent
  })
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [connectionState, setConnectionState] = useState<PipelineConnectionState>('connecting')

  const idsKey = useMemo(() => artifactIds?.sort().join(',') ?? '', [artifactIds])

  useEffect(() => {
    const ids = idsKey ? idsKey.split(',') : []
    const params = ids.length === 1
      ? `?artifact_id=${ids[0]}`
      : ''
    // Connect directly to API for SSE (Vite proxy buffers event streams)
    const sseBase = import.meta.env.VITE_SSE_URL || ''
    const url = `${sseBase}/api/uploads/pipeline-events${params}`

    if (typeof EventSource === 'undefined') return

    let disposed = false
    let source: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let backoffMs = MIN_BACKOFF_MS

    const handlePipeline = (event: MessageEvent) => {
      let data: PipelineEvent
      try {
        data = JSON.parse(event.data) as PipelineEvent
      } catch (err) {
        // A malformed frame must not tear down the stream - skip it.
        logRawError(err)
        return
      }
      if (ids.length === 0 || ids.includes(data.artifact_id)) {
        // Stamp receipt time so consumers can derive per-stage durations
        const stamped = { ...data, receivedAt: Date.now() }
        setEvents((prev) => [...prev, stamped].slice(-MAX_EVENTS))
        onEventRef.current?.(stamped)
      }
    }

    const connect = () => {
      if (disposed) return
      source = new EventSource(url)
      source.addEventListener('pipeline', handlePipeline)
      source.onopen = () => {
        backoffMs = MIN_BACKOFF_MS
        setConnectionState('open')
      }
      source.onerror = () => {
        if (disposed) return
        source?.close()
        source = null
        setConnectionState('reconnecting')
        retryTimer = setTimeout(() => {
          retryTimer = null
          connect()
        }, backoffMs)
        backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS)
      }
    }

    connect()

    return () => {
      disposed = true
      if (retryTimer) clearTimeout(retryTimer)
      source?.close()
    }
  }, [idsKey])

  const clear = () => setEvents([])

  return {
    events,
    connectionState,
    connected: connectionState === 'open',
    clear,
  }
}

import { useEffect, useMemo, useState } from 'react'
import type { PipelineEvent } from '../types'

export type PipelineConnectionState = 'connecting' | 'open' | 'reconnecting'

// Keep memory bounded on long pipeline sessions
const MAX_EVENTS = 200
const MIN_BACKOFF_MS = 1_000
const MAX_BACKOFF_MS = 30_000

export function usePipelineEvents(artifactIds?: string[]) {
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

    let disposed = false
    let source: EventSource | null = null
    let retryTimer: ReturnType<typeof setTimeout> | null = null
    let backoffMs = MIN_BACKOFF_MS

    const handlePipeline = (event: MessageEvent) => {
      const data = JSON.parse(event.data) as PipelineEvent
      if (ids.length === 0 || ids.includes(data.artifact_id)) {
        setEvents((prev) => [...prev, data].slice(-MAX_EVENTS))
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

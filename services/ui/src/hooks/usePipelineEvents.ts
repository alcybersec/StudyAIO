import { useEffect, useRef, useState } from 'react'
import type { PipelineEvent } from '../types'

export function usePipelineEvents(artifactId?: string) {
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [connected, setConnected] = useState(false)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const params = artifactId ? `?artifact_id=${artifactId}` : ''
    const url = `/api/uploads/pipeline-events${params}`

    const source = new EventSource(url)
    sourceRef.current = source

    source.addEventListener('pipeline', (event) => {
      const data = JSON.parse(event.data) as PipelineEvent
      setEvents((prev) => [...prev, data])
    })

    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)

    return () => {
      source.close()
      sourceRef.current = null
      setConnected(false)
    }
  }, [artifactId])

  const clear = () => setEvents([])

  return { events, connected, clear }
}

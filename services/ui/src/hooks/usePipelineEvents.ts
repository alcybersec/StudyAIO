import { useEffect, useMemo, useRef, useState } from 'react'
import type { PipelineEvent } from '../types'

export function usePipelineEvents(artifactIds?: string[]) {
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [connected, setConnected] = useState(false)
  const sourceRef = useRef<EventSource | null>(null)

  const idsKey = useMemo(() => artifactIds?.sort().join(',') ?? '', [artifactIds])

  useEffect(() => {
    const ids = idsKey ? idsKey.split(',') : []
    const params = ids.length === 1
      ? `?artifact_id=${ids[0]}`
      : ''
    const url = `/api/uploads/pipeline-events${params}`

    const source = new EventSource(url)
    sourceRef.current = source

    source.addEventListener('pipeline', (event) => {
      const data = JSON.parse(event.data) as PipelineEvent
      if (ids.length === 0 || ids.includes(data.artifact_id)) {
        setEvents((prev) => [...prev, data])
      }
    })

    source.onopen = () => setConnected(true)
    source.onerror = () => setConnected(false)

    return () => {
      source.close()
      sourceRef.current = null
      setConnected(false)
    }
  }, [idsKey])

  const clear = () => setEvents([])

  return { events, connected, clear }
}

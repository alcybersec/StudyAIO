import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { usePipelineEvents } from '../hooks/usePipelineEvents'
import type { PipelineEvent } from '../types'
import {
  PipelineEventsContext,
  countActiveArtifacts,
  isTerminalEvent,
  type TrackedUpload,
} from './pipelineProgress'

const MAX_TRACKED = 50

/**
 * Owns the one pipeline SSE connection for the whole app shell, so progress
 * keeps updating while the user is on other pages, and refreshes the course /
 * week / dashboard queries when an artifact finishes.
 */
export function PipelineEventsProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [uploads, setUploads] = useState<TrackedUpload[]>([])

  const onEvent = useCallback(
    (event: PipelineEvent) => {
      if (!isTerminalEvent(event)) return
      queryClient.invalidateQueries({ queryKey: ['courses'] }) // course list, week views, week badge
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['review-items'] })
      queryClient.invalidateQueries({ queryKey: ['assets'] })
    },
    [queryClient],
  )

  const { events, connectionState } = usePipelineEvents(undefined, onEvent)

  const track = useCallback((upload: TrackedUpload) => {
    setUploads((prev) =>
      prev.some((u) => u.key === upload.key) ? prev : [...prev, upload].slice(-MAX_TRACKED),
    )
  }, [])

  const value = useMemo(
    () => ({ events, connectionState, uploads, activeCount: countActiveArtifacts(events), track }),
    [events, connectionState, uploads, track],
  )

  return <PipelineEventsContext.Provider value={value}>{children}</PipelineEventsContext.Provider>
}

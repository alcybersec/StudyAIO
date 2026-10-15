import { createContext, useContext } from 'react'
import type { PipelineConnectionState } from '../hooks/usePipelineEvents'
import type { PipelineEvent } from '../types'

/** A file the user uploaded this session; survives leaving the Upload page. */
export interface TrackedUpload {
  key: string
  name: string
  sizeBytes: number
  artifactId: string
  /** Uploaded with an explicit course + week: no ingest/classify events will arrive. */
  placed?: boolean
}

export interface PipelineEventsValue {
  events: PipelineEvent[]
  connectionState: PipelineConnectionState
  uploads: TrackedUpload[]
  /** Artifacts that have started but not yet reached a terminal event. */
  activeCount: number
  track: (upload: TrackedUpload) => void
}

export const PipelineEventsContext = createContext<PipelineEventsValue | null>(null)

/** assets is the last stage; a failure or a review hold also ends the run. */
export function isTerminalEvent(event: PipelineEvent): boolean {
  if (event.status === 'failed' || event.status === 'waiting_review') return true
  return event.stage === 'assets' && event.status !== 'started' && event.status !== 'running'
}

/** Count artifacts whose latest event is not terminal. */
export function countActiveArtifacts(events: PipelineEvent[]): number {
  const latest = new Map<string, PipelineEvent>()
  for (const e of events) latest.set(e.artifact_id, e)
  let n = 0
  for (const e of latest.values()) if (!isTerminalEvent(e)) n++
  return n
}

export function usePipelineProgress(): PipelineEventsValue {
  const ctx = useContext(PipelineEventsContext)
  if (!ctx) throw new Error('usePipelineProgress must be used inside PipelineEventsProvider')
  return ctx
}

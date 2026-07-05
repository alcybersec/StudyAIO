import type { PipelineEvent } from '../types'

export const PIPELINE_STAGE_NAMES = [
  'ingest',
  'classify',
  'extract',
  'summarize',
  'index',
  'assets',
] as const

export type PipelineStageName = (typeof PIPELINE_STAGE_NAMES)[number]

export type StageStatus = 'pending' | 'running' | 'done' | 'failed'

export interface PipelineStage {
  name: PipelineStageName
  status: StageStatus
  /** Wall-clock duration between the stage's started and terminal event. */
  ms?: number
  error?: string
}

const RUNNING_STATUSES = new Set(['started', 'running'])

/**
 * Fold an ordered SSE event stream into the six-stage rail model.
 *
 * Later events win per stage, so a retried stage that failed and then
 * restarted shows as running again. Events for unknown stages are ignored.
 * Durations come from the client-side `receivedAt` stamps applied by
 * usePipelineEvents; events without stamps simply omit the timing.
 */
export function mapPipelineEventsToStages(events: PipelineEvent[]): PipelineStage[] {
  const stages = new Map<PipelineStageName, PipelineStage>(
    PIPELINE_STAGE_NAMES.map((name) => [name, { name, status: 'pending' as StageStatus }]),
  )
  const startedAt = new Map<PipelineStageName, number | undefined>()

  for (const event of events) {
    const name = event.stage as PipelineStageName
    const stage = stages.get(name)
    if (!stage) continue // unknown stage — ignore

    if (RUNNING_STATUSES.has(event.status)) {
      startedAt.set(name, event.receivedAt)
      stages.set(name, { name, status: 'running' })
      continue
    }

    const began = startedAt.get(name)
    const ms = began !== undefined && event.receivedAt !== undefined ? Math.max(0, event.receivedAt - began) : undefined

    if (event.status === 'failed') {
      stages.set(name, { name, status: 'failed', ms, error: event.message ?? 'Stage failed' })
    } else {
      // completed, skipped, waiting_review, … — the stage finished its run
      stages.set(name, { name, status: 'done', ms })
    }
  }

  return PIPELINE_STAGE_NAMES.map((name) => stages.get(name)!)
}

/** "850ms" under a second, "1.2s" above. */
export function formatStageMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`
}

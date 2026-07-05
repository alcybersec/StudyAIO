import { describe, expect, it } from 'vitest'
import { formatStageMs, mapPipelineEventsToStages, PIPELINE_STAGE_NAMES } from './pipelineStages'
import type { PipelineEvent } from '../types'

const ev = (
  stage: string,
  status: string,
  overrides: Partial<PipelineEvent> = {},
): PipelineEvent => ({
  artifact_id: 'a1',
  stage,
  status,
  message: null,
  ...overrides,
})

describe('mapPipelineEventsToStages', () => {
  it('returns all six stages pending for an empty stream', () => {
    const stages = mapPipelineEventsToStages([])
    expect(stages.map((s) => s.name)).toEqual([...PIPELINE_STAGE_NAMES])
    expect(stages.every((s) => s.status === 'pending')).toBe(true)
  })

  it('marks a stage running on started', () => {
    const stages = mapPipelineEventsToStages([ev('ingest', 'started')])
    expect(stages[0]).toMatchObject({ name: 'ingest', status: 'running' })
  })

  it('started then completed yields done with a duration', () => {
    const stages = mapPipelineEventsToStages([
      ev('ingest', 'started', { receivedAt: 1_000 }),
      ev('ingest', 'completed', { receivedAt: 2_250 }),
    ])
    expect(stages[0]).toMatchObject({ name: 'ingest', status: 'done', ms: 1_250 })
  })

  it('started then failed yields failed with error text and duration', () => {
    const stages = mapPipelineEventsToStages([
      ev('extract', 'started', { receivedAt: 500 }),
      ev('extract', 'failed', { receivedAt: 900, message: 'PDF is encrypted' }),
    ])
    expect(stages[2]).toMatchObject({
      name: 'extract',
      status: 'failed',
      ms: 400,
      error: 'PDF is encrypted',
    })
  })

  it('failed without a message gets a generic error', () => {
    const stages = mapPipelineEventsToStages([ev('classify', 'failed')])
    expect(stages[1]).toMatchObject({ status: 'failed', error: 'Stage failed' })
  })

  it('a retried stage goes back to running and clears the error', () => {
    const stages = mapPipelineEventsToStages([
      ev('summarize', 'started'),
      ev('summarize', 'failed', { message: 'timeout' }),
      ev('summarize', 'started'),
    ])
    expect(stages[3]).toMatchObject({ name: 'summarize', status: 'running' })
    expect(stages[3].error).toBeUndefined()
  })

  it('non-failed terminal statuses (skipped, waiting_review) count as done', () => {
    const stages = mapPipelineEventsToStages([
      ev('classify', 'started'),
      ev('classify', 'waiting_review'),
      ev('index', 'skipped'),
    ])
    expect(stages[1].status).toBe('done')
    expect(stages[4].status).toBe('done')
  })

  it('ignores events for unknown stages', () => {
    const stages = mapPipelineEventsToStages([
      ev('teleport', 'started'),
      ev('', 'completed'),
      ev('ingest', 'completed'),
    ])
    expect(stages[0].status).toBe('done')
    expect(stages.slice(1).every((s) => s.status === 'pending')).toBe(true)
  })

  it('omits duration when timestamps are missing', () => {
    const stages = mapPipelineEventsToStages([
      ev('ingest', 'started'),
      ev('ingest', 'completed', { receivedAt: 5_000 }),
    ])
    expect(stages[0].status).toBe('done')
    expect(stages[0].ms).toBeUndefined()
  })

  it('a full pipeline sequence maps each stage independently', () => {
    const events = [
      ev('ingest', 'started', { receivedAt: 0 }),
      ev('ingest', 'completed', { receivedAt: 100 }),
      ev('classify', 'started', { receivedAt: 100 }),
      ev('classify', 'completed', { receivedAt: 1_400 }),
      ev('extract', 'started', { receivedAt: 1_400 }),
    ]
    const stages = mapPipelineEventsToStages(events)
    expect(stages.map((s) => s.status)).toEqual(['done', 'done', 'running', 'pending', 'pending', 'pending'])
    expect(stages[1].ms).toBe(1_300)
  })
})

describe('formatStageMs', () => {
  it('formats sub-second as ms and above as seconds', () => {
    expect(formatStageMs(850)).toBe('850ms')
    expect(formatStageMs(999)).toBe('999ms')
    expect(formatStageMs(1_000)).toBe('1.0s')
    expect(formatStageMs(12_340)).toBe('12.3s')
  })
})

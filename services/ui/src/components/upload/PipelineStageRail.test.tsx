import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PipelineStageRail } from './PipelineStageRail'
import type { PipelineStage } from '../../lib/pipelineStages'

const stages: PipelineStage[] = [
  { name: 'ingest', status: 'done', ms: 320 },
  { name: 'classify', status: 'done', ms: 1_500 },
  { name: 'extract', status: 'failed', ms: 90, error: 'PDF is encrypted' },
  { name: 'summarize', status: 'running' },
  { name: 'index', status: 'pending' },
  { name: 'assets', status: 'pending' },
]

describe('PipelineStageRail', () => {
  it('renders one list item per stage with its status', () => {
    render(<PipelineStageRail stages={stages} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(6)
    expect(screen.getByLabelText('ingest: done')).toBeInTheDocument()
    expect(screen.getByLabelText('extract: failed')).toBeInTheDocument()
    expect(screen.getByLabelText('summarize: running')).toBeInTheDocument()
    expect(screen.getByLabelText('assets: pending')).toBeInTheDocument()
  })

  it('shows per-stage timings in ms or seconds', () => {
    render(<PipelineStageRail stages={stages} />)
    expect(screen.getByText('320ms')).toBeInTheDocument()
    expect(screen.getByText('1.5s')).toBeInTheDocument()
  })

  it('renders no timing text for stages without a duration', () => {
    render(<PipelineStageRail stages={stages} />)
    const running = screen.getByLabelText('summarize: running')
    expect(running.textContent).toBe('summarize')
  })
})

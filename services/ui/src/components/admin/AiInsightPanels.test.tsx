import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AiFeedbackPanel } from './AiFeedbackPanel'
import { RetentionPanel } from './RetentionPanel'
import { useAdminAiFeedback, useAdminRetention } from '../../hooks/useApi'
import type { AIFeedbackSummary, RetentionReadout } from '../../types'

vi.mock('../../hooks/useApi', () => ({ useAdminAiFeedback: vi.fn(), useAdminRetention: vi.fn() }))

const asResult = (q: object) => q as never
const loading = { data: undefined, isLoading: true, isError: false, refetch: vi.fn() }
const failed = { data: undefined, isLoading: false, isError: true, refetch: vi.fn() }
const ok = (data: unknown) => ({ data, isLoading: false, isError: false, refetch: vi.fn() })

beforeEach(() => vi.clearAllMocks())

describe('AiFeedbackPanel', () => {
  const data: AIFeedbackSummary = {
    total: 5,
    by_target_type: { summary: { up: 2, down: 1 }, flashcard: { up: 0, down: 2 } },
    by_reason: { inaccurate: 2 },
    by_rating: { '1': 3, '-1': 2 },
    recent_negative: [
      { target_type: 'summary', reason: 'inaccurate', comment: 'wrong formula', course_id: null, created_at: '2026-10-09T10:00:00Z' },
    ],
  }

  it('shows a skeleton while loading', () => {
    vi.mocked(useAdminAiFeedback).mockReturnValue(asResult(loading))
    const { container } = render(<AiFeedbackPanel />)
    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument()
  })

  it('shows a retryable error', async () => {
    vi.mocked(useAdminAiFeedback).mockReturnValue(asResult(failed))
    render(<AiFeedbackPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent(/AI feedback couldn't load/)
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(failed.refetch).toHaveBeenCalled()
  })

  it('says so when there is no feedback', () => {
    vi.mocked(useAdminAiFeedback).mockReturnValue(
      asResult(ok({ total: 0, by_target_type: {}, by_reason: {}, by_rating: {}, recent_negative: [] })),
    )
    render(<AiFeedbackPanel />)
    expect(screen.getByText('No AI feedback in this period yet.')).toBeInTheDocument()
  })

  it('shows totals, breakdowns and recent comments without user identities', () => {
    vi.mocked(useAdminAiFeedback).mockReturnValue(asResult(ok(data)))
    render(<AiFeedbackPanel />)
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('Summaries')).toBeInTheDocument()
    // Per-type votes render as up/down counts, not as one number.
    const summaries = screen.getByText('Summaries').closest('li') as HTMLElement
    expect(summaries).toHaveTextContent('2')
    expect(summaries).toHaveTextContent('1')
    expect(within(summaries).getByLabelText('Helpful: 2')).toBeInTheDocument()
    expect(within(summaries).getByLabelText('Not helpful: 1')).toBeInTheDocument()
    expect(screen.getByText('Not helpful')).toBeInTheDocument()
    expect(screen.getByText('wrong formula')).toBeInTheDocument()
    expect(vi.mocked(useAdminAiFeedback)).toHaveBeenCalledWith(30)
  })
})

describe('RetentionPanel', () => {
  const data: RetentionReadout = {
    cohorts: [
      { week_start: '2026-09-28', signups: 10, d1: 6, d7: 3, d30: null },
      { week_start: '2026-10-05', signups: 4, d1: null, d7: null, d30: null },
    ],
    features: [
      { week_start: '2026-10-05', event: 'summary_viewed', active_users: 7 },
      { week_start: '2026-09-28', event: 'summary_viewed', active_users: 5 },
    ],
  }

  it('shows a skeleton while loading', () => {
    vi.mocked(useAdminRetention).mockReturnValue(asResult(loading))
    const { container } = render(<RetentionPanel />)
    expect(container.querySelector('[aria-busy="true"]')).toBeInTheDocument()
  })

  it('shows a retryable error', async () => {
    vi.mocked(useAdminRetention).mockReturnValue(asResult(failed))
    render(<RetentionPanel />)
    expect(screen.getByRole('alert')).toHaveTextContent(/Retention couldn't load/)
    await userEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(failed.refetch).toHaveBeenCalled()
  })

  it('says so when there is nothing yet', () => {
    vi.mocked(useAdminRetention).mockReturnValue(asResult(ok({ cohorts: [], features: [] })))
    render(<RetentionPanel />)
    expect(screen.getByText('No usage data in this period yet.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('renders cohorts with nulls as a dash', () => {
    vi.mocked(useAdminRetention).mockReturnValue(asResult(ok(data)))
    render(<RetentionPanel />)
    const rows = screen.getAllByRole('row')
    // header + two cohorts
    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('2026-09-28')
    expect(rows[1]).toHaveTextContent('6 (60%)')
    expect(rows[1]).toHaveTextContent('3 (30%)')
    expect(rows[1].textContent).toContain('—')
    expect(rows[2].textContent?.match(/—/g)).toHaveLength(3)
    expect(vi.mocked(useAdminRetention)).toHaveBeenCalledWith(8)
  })

  it('lists weekly actives per feature, oldest week first', () => {
    vi.mocked(useAdminRetention).mockReturnValue(asResult(ok(data)))
    render(<RetentionPanel />)
    const feature = screen.getByText('summary_viewed').closest('li')!
    expect(feature.textContent).toMatch(/09-28: 5.*10-05: 7/)
  })
})

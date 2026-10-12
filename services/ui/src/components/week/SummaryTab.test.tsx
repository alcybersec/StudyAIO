import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SummaryTab } from './SummaryTab'
import { recordUsageEvent } from '../../api/usage'
import type { SummaryData } from '../../types'

vi.mock('../../api/usage', () => ({ recordUsageEvent: vi.fn() }))
vi.mock('../../api/aiFeedback', () => ({
  aiFeedbackApi: { mine: vi.fn().mockResolvedValue([]), put: vi.fn(), clear: vi.fn() },
}))

function summary(content_md: string): SummaryData {
  return {
    id: 'sum1',
    course_id: 'course1',
    week: 2,
    content_md,
    version: 1,
    source_artifacts: ['a1'],
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  }
}

function setup(md: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SummaryTab summary={summary(md)} />
    </QueryClientProvider>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('SummaryTab citations', () => {
  it('renders [p.3] as a focusable chip titled "Page 3"', () => {
    setup('Quicksort is O(n log n) on average [p.3].')
    const chip = screen.getByRole('note', { name: 'Page 3' })
    expect(chip).toHaveTextContent('p.3')
    expect(chip).toHaveAttribute('tabindex', '0')
    expect(chip).toHaveAttribute('title', 'Page 3')
  })

  it('renders [D2 p.1] with the document in the title', () => {
    setup('Merged claim [D2 p.1].')
    const chip = screen.getByRole('note', { name: 'Document 2, page 1' })
    expect(chip).toHaveTextContent('D2 p.1')
  })

  it('renders adjacent markers and markers inside list items and tables', () => {
    setup('- item [p.2][p.3]\n\n| a | b |\n|---|---|\n| x [p.7] | y |\n')
    expect(screen.getAllByRole('note').map((n) => n.textContent)).toEqual(['p.2', 'p.3', 'p.7'])
  })

  it('leaves code blocks and inline code untouched', () => {
    setup('```\narr[p.3] = 1\n```\n\nUse `[p.4]` literally.')
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(screen.getByText('arr[p.3] = 1')).toBeInTheDocument()
    expect(screen.getByText('[p.4]')).toBeInTheDocument()
  })

  it('leaves ordinary brackets alone', () => {
    setup('See [the docs](https://example.com) and [p3] and [page 3].')
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
    expect(screen.getByText(/\[p3\] and \[page 3\]/)).toBeInTheDocument()
  })
})

describe('SummaryTab events and feedback', () => {
  it('records one summary_viewed event with the course id', () => {
    const { rerender } = setup('Hello')
    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <SummaryTab summary={summary('Hello again')} />
      </QueryClientProvider>,
    )
    expect(recordUsageEvent).toHaveBeenCalledTimes(1)
    expect(recordUsageEvent).toHaveBeenCalledWith('summary_viewed', 'course1')
  })

  it('offers thumbs up/down on the summary', () => {
    setup('Hello')
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeInTheDocument()
  })
})

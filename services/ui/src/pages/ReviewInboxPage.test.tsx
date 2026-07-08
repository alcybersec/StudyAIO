import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ReviewInboxPage } from './ReviewInboxPage'
import type { ReviewItem } from '../types'

const mockUseReviewItems = vi.fn()
const mockUsePendingReviews = vi.fn()
const mockUseCourses = vi.fn()
const mockResolveMutateAsync = vi.fn()
const mockDismissMutateAsync = vi.fn()

vi.mock('../hooks/useApi', () => ({
  useReviewItems: (status: string) => mockUseReviewItems(status),
  usePendingReviews: () => mockUsePendingReviews(),
  useCourses: () => mockUseCourses(),
  useResolveReview: () => ({ mutateAsync: mockResolveMutateAsync, isPending: false }),
  useDismissReview: () => ({ mutateAsync: mockDismissMutateAsync, isPending: false }),
}))

vi.mock('../hooks/useOnlineStatus', () => ({
  useOnlineStatus: () => true,
}))

function makeItem(id: string, filename: string): ReviewItem {
  return {
    id,
    review_type: 'classification_course',
    entity_type: 'lecture_artifact',
    entity_id: `artifact-${id}`,
    payload_json: {
      filename,
      reason: 'Classification confidence below threshold',
      suggestions: [{ value: {}, confidence: 0.35 }],
    },
    suggested_values: { course_code: 'CSIT302', week: 3 },
    status: 'pending',
    resolution_json: null,
    created_at: '2026-07-01T10:00:00Z',
    resolved_at: null,
  }
}

const items = [
  makeItem('r1', 'lec01_intro.pdf'),
  makeItem('r2', 'lec02_stacks.pdf'),
  makeItem('r3', 'lec03_queues.pdf'),
]

function setup() {
  mockUseReviewItems.mockReturnValue({
    data: items,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })
  mockUsePendingReviews.mockReturnValue({ data: items })
  mockUseCourses.mockReturnValue({
    data: [{ id: 'c1', code: 'CSIT302', name: 'Cybersecurity', weeks_covered: 9 }],
  })
  return render(
    <MemoryRouter>
      <ReviewInboxPage />
    </MemoryRouter>,
  )
}

function focusedRow(): HTMLElement | null {
  return document.querySelector('li[aria-current="true"]')
}

beforeEach(() => {
  vi.clearAllMocks()
  mockResolveMutateAsync.mockResolvedValue({})
  mockDismissMutateAsync.mockResolvedValue({})
})

describe('ReviewInboxPage keyboard triage', () => {
  it('moves the focused row with j/k and clamps at the ends', async () => {
    const user = userEvent.setup()
    setup()

    expect(focusedRow()).toHaveTextContent('lec01_intro.pdf')

    await user.keyboard('j')
    expect(focusedRow()).toHaveTextContent('lec02_stacks.pdf')

    await user.keyboard('j')
    await user.keyboard('j') // clamped at the last row
    expect(focusedRow()).toHaveTextContent('lec03_queues.pdf')

    await user.keyboard('k')
    await user.keyboard('k')
    await user.keyboard('k') // clamped at the first row
    expect(focusedRow()).toHaveTextContent('lec01_intro.pdf')
  })

  it('approves the focused item with a', async () => {
    const user = userEvent.setup()
    setup()

    await user.keyboard('j')
    await user.keyboard('a')

    expect(mockResolveMutateAsync).toHaveBeenCalledTimes(1)
    expect(mockResolveMutateAsync).toHaveBeenCalledWith({
      reviewId: 'r2',
      resolution: { course_code: 'CSIT302', week: 3 },
    })
  })

  it('dismisses the focused item with d', async () => {
    const user = userEvent.setup()
    setup()

    await user.keyboard('d')
    expect(mockDismissMutateAsync).toHaveBeenCalledWith('r1')
  })

  it('ignores triage keys while the inline editor is open', async () => {
    const user = userEvent.setup()
    setup()

    await user.keyboard('e')
    expect(screen.getByLabelText('Week')).toBeInTheDocument()

    // Single-key triage shortcuts are inert while editing…
    await user.keyboard('a')
    await user.keyboard('d')
    expect(mockResolveMutateAsync).not.toHaveBeenCalled()
    expect(mockDismissMutateAsync).not.toHaveBeenCalled()

    // …and typing letters in the week input never moves focus or fires actions.
    const weekInput = screen.getByLabelText('Week')
    await user.click(weekInput)
    await user.keyboard('jad')
    expect(focusedRow()).toHaveTextContent('lec01_intro.pdf')
    expect(mockResolveMutateAsync).not.toHaveBeenCalled()
    expect(mockDismissMutateAsync).not.toHaveBeenCalled()

    // Escape closes the editor and triage keys work again.
    await user.keyboard('{Escape}')
    expect(screen.queryByLabelText('Week')).not.toBeInTheDocument()
    await user.keyboard('j')
    expect(focusedRow()).toHaveTextContent('lec02_stacks.pdf')
  })
})

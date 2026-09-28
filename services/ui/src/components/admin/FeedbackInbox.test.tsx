import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FeedbackInbox } from './FeedbackInbox'
import { useAdminFeedback, useSetFeedbackStatus } from '../../hooks/useApi'
import type { FeedbackList } from '../../types'

vi.mock('../../hooks/useApi', () => ({
  useAdminFeedback: vi.fn(),
  useSetFeedbackStatus: vi.fn(),
}))

const asResult = (q: object) => q as never
const setStatus = vi.fn()

const ITEM = {
  id: 'f-1',
  kind: 'bug' as const,
  message: 'Summary tab renders empty',
  route: '/courses/CSIT302/weeks/3',
  app_version: '8d8841b',
  status: 'new' as const,
  created_at: null,
  user_email: 'tester@example.com',
}

function withData(data: Partial<FeedbackList> = {}) {
  vi.mocked(useAdminFeedback).mockReturnValue(
    asResult({
      data: {
        items: [ITEM],
        total: 1,
        offset: 0,
        limit: 50,
        counts: { new: 1, triaged: 0, closed: 0 },
        ...data,
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useSetFeedbackStatus).mockReturnValue(asResult({ mutate: setStatus, isPending: false }))
})

describe('FeedbackInbox', () => {
  it('shows what the reporter wrote', () => {
    withData()
    render(<FeedbackInbox />)

    expect(screen.getByText('Summary tab renders empty')).toBeInTheDocument()
  })

  it('shows the route and build, which are what make it reproducible', () => {
    withData()
    render(<FeedbackInbox />)

    expect(screen.getByText('/courses/CSIT302/weeks/3')).toBeInTheDocument()
    expect(screen.getByText('8d8841b')).toBeInTheDocument()
  })

  it('badges how much is unread', () => {
    withData()
    render(<FeedbackInbox />)

    expect(screen.getByText(/1 new/i)).toBeInTheDocument()
  })

  it('hides the badge when nothing is new', () => {
    withData({ counts: { new: 0, triaged: 2, closed: 5 } })
    render(<FeedbackInbox />)

    // Match the badge specifically — "New" is also a filter button.
    expect(screen.queryByText(/^\d+ new$/i)).not.toBeInTheDocument()
  })

  it('defaults to the new filter, since that is the actionable one', () => {
    withData()
    render(<FeedbackInbox />)

    expect(vi.mocked(useAdminFeedback)).toHaveBeenLastCalledWith('new')
  })

  it('can show everything', async () => {
    withData()
    render(<FeedbackInbox />)
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /^all$/i }))

    expect(vi.mocked(useAdminFeedback)).toHaveBeenLastCalledWith(undefined)
  })

  it('triages an item', async () => {
    withData()
    render(<FeedbackInbox />)
    const user = userEvent.setup()

    // Scope to the item: "Triaged" is also a filter button.
    const item = screen.getByRole('listitem')
    await user.click(within(item).getByRole('button', { name: /triaged/i }))

    expect(setStatus).toHaveBeenCalledWith({ id: 'f-1', status: 'triaged' })
  })

  it('does not offer the state an item is already in', () => {
    withData({ items: [{ ...ITEM, status: 'closed' }] })
    render(<FeedbackInbox />)

    expect(screen.queryByRole('button', { name: /^close$/i })).not.toBeInTheDocument()
  })

  it('says so when there is nothing rather than rendering an empty box', () => {
    withData({ items: [], counts: { new: 0, triaged: 0, closed: 0 } })
    render(<FeedbackInbox />)

    expect(screen.getByText(/nothing new/i)).toBeInTheDocument()
  })

  it('shows an error state instead of a blank panel', () => {
    vi.mocked(useAdminFeedback).mockReturnValue(
      asResult({ data: undefined, isLoading: false, isError: true, refetch: vi.fn() }),
    )
    render(<FeedbackInbox />)

    expect(screen.getByText(/couldn't load/i)).toBeInTheDocument()
  })
})

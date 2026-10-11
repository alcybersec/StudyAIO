import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AiFeedbackControl } from './AiFeedbackControl'
import { aiFeedbackApi } from '../../api/aiFeedback'
import { NotFoundError } from '../../api/errors'
import type { AIFeedbackVote } from '../../types'

vi.mock('../../api/aiFeedback', () => ({
  aiFeedbackApi: { mine: vi.fn(), put: vi.fn(), clear: vi.fn() },
}))
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

const api = vi.mocked(aiFeedbackApi)

function vote(over: Partial<AIFeedbackVote> = {}): AIFeedbackVote {
  return { target_type: 'summary', target_id: 's1', rating: 1, reason: null, comment: null, ...over }
}

function setup(props: Partial<React.ComponentProps<typeof AiFeedbackControl>> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AiFeedbackControl targetType="summary" targetId="s1" {...props} />
    </QueryClientProvider>,
  )
}

const up = () => screen.getByRole('button', { name: 'Helpful' })
const down = () => screen.getByRole('button', { name: 'Not helpful' })

beforeEach(() => {
  vi.clearAllMocks()
  api.mine.mockResolvedValue([])
  api.put.mockResolvedValue(vote())
  api.clear.mockResolvedValue(undefined)
})

describe('AiFeedbackControl', () => {
  it('starts unpressed and loads the caller vote in one batch', async () => {
    api.mine.mockResolvedValue([vote({ target_id: 'b', rating: -1 }), vote({ target_id: 'a', rating: 1 })])
    setup({ targetType: 'flashcard', targetId: 'a', batchIds: ['b', 'a'] })

    await waitFor(() => expect(up()).toHaveAttribute('aria-pressed', 'true'))
    expect(down()).toHaveAttribute('aria-pressed', 'false')
    expect(api.mine).toHaveBeenCalledTimes(1)
    expect(api.mine).toHaveBeenCalledWith('flashcard', ['a', 'b'])
  })

  it('thumbs up is optimistic and sent as rating 1', async () => {
    let release: () => void = () => {}
    api.put.mockReturnValue(new Promise((r) => (release = () => r(vote()))))
    setup()
    await waitFor(() => expect(api.mine).toHaveBeenCalled())

    await userEvent.click(up())

    expect(up()).toHaveAttribute('aria-pressed', 'true') // before the server answered
    expect(api.put).toHaveBeenCalledWith({ target_type: 'summary', target_id: 's1', rating: 1 })
    release()
  })

  it('rolls back and reports when the save fails', async () => {
    const { toast } = await import('sonner')
    api.put.mockRejectedValue(new Error('boom'))
    setup()
    await waitFor(() => expect(api.mine).toHaveBeenCalled())

    await userEvent.click(up())

    await waitFor(() => expect(up()).toHaveAttribute('aria-pressed', 'false'))
    expect(toast.error).toHaveBeenCalled()
  })

  it('pressing a pressed thumb clears the vote', async () => {
    api.mine.mockResolvedValue([vote()])
    setup()
    await waitFor(() => expect(up()).toHaveAttribute('aria-pressed', 'true'))

    await userEvent.click(up())

    expect(up()).toHaveAttribute('aria-pressed', 'false')
    expect(api.clear).toHaveBeenCalledWith('summary', 's1')
  })

  it('treats a 404 on clear as already cleared', async () => {
    const { toast } = await import('sonner')
    api.mine.mockResolvedValue([vote()])
    api.clear.mockRejectedValue(new NotFoundError('gone', 404))
    setup()
    await waitFor(() => expect(up()).toHaveAttribute('aria-pressed', 'true'))

    await userEvent.click(up())

    await waitFor(() => expect(api.clear).toHaveBeenCalled())
    expect(up()).toHaveAttribute('aria-pressed', 'false')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('thumbs down opens the reason picker without saving yet', async () => {
    setup()
    await userEvent.click(down())

    expect(screen.getByRole('group', { name: "What wasn't right?" })).toBeInTheDocument()
    for (const r of ['Inaccurate', 'Not in my lectures', 'Unclear', 'Wrong format', 'Other']) {
      expect(screen.getByRole('radio', { name: r })).toBeInTheDocument()
    }
    expect(api.put).not.toHaveBeenCalled()
  })

  it('sends rating -1 with the chosen reason and a comment', async () => {
    setup()
    await userEvent.click(down())
    await userEvent.click(screen.getByRole('radio', { name: 'Not in my lectures' }))
    await userEvent.type(screen.getByLabelText('Comment (optional)'), 'covers week 5')
    await userEvent.click(screen.getByRole('button', { name: 'Send feedback' }))

    expect(api.put).toHaveBeenCalledWith({
      target_type: 'summary',
      target_id: 's1',
      rating: -1,
      reason: 'not_in_my_lectures',
      comment: 'covers week 5',
    })
    expect(down()).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByRole('group', { name: "What wasn't right?" })).not.toBeInTheDocument()
  })

  it('caps the comment at 1000 characters', async () => {
    setup()
    await userEvent.click(down())
    expect(screen.getByLabelText('Comment (optional)')).toHaveAttribute('maxlength', '1000')
  })

  it('can send a thumbs down with no reason', async () => {
    setup()
    await userEvent.click(down())
    await userEvent.click(screen.getByRole('button', { name: 'Send feedback' }))
    expect(api.put).toHaveBeenCalledWith({ target_type: 'summary', target_id: 's1', rating: -1 })
  })

  it('cancel closes the picker and saves nothing', async () => {
    setup()
    await userEvent.click(down())
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('group', { name: "What wasn't right?" })).not.toBeInTheDocument()
    expect(api.put).not.toHaveBeenCalled()
  })
})

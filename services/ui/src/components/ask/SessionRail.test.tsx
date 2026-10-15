import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SessionRail } from './SessionRail'
import type { ChatSession } from '../../types'

const mutate = vi.fn()
vi.mock('../../hooks/useApi', () => ({
  useDeleteChatSession: () => ({ mutate, isPending: false }),
}))

const session = {
  id: 's1',
  title: 'Photosynthesis basics',
  message_count: 4,
  updated_at: new Date().toISOString(),
} as ChatSession

function setup() {
  render(
    <SessionRail sessions={[session]} selectedId="s1" onSelect={vi.fn()} onNewQuestion={vi.fn()} isCreating={false} />,
  )
}

describe('SessionRail delete confirmation', () => {
  beforeEach(() => mutate.mockReset())

  it('opens a dialog naming the conversation, with Cancel focused', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: 'Delete conversation' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveTextContent('Photosynthesis basics')
    expect(dialog).toHaveTextContent('4')
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
    expect(mutate).not.toHaveBeenCalled()
  })

  it('a double-click on the trash icon deletes nothing', async () => {
    const user = userEvent.setup()
    setup()
    await user.dblClick(screen.getByRole('button', { name: 'Delete conversation' }))
    expect(mutate).not.toHaveBeenCalled()
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('Cancel closes without deleting', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: 'Delete conversation' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mutate).not.toHaveBeenCalled()
  })

  it('Enter on the default focus cancels and Escape closes; neither deletes', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: 'Delete conversation' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Delete conversation' }))
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(mutate).not.toHaveBeenCalled()
  })

  it('Delete deletes exactly that session', async () => {
    const user = userEvent.setup()
    setup()
    await user.click(screen.getByRole('button', { name: 'Delete conversation' }))
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(mutate).toHaveBeenCalledTimes(1)
    expect(mutate.mock.calls[0][0]).toBe('s1')
  })
})

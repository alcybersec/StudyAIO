import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NotificationsSection } from './NotificationsSection'
import {
  useNotificationPreferences,
  useUpdatePreferences,
  useTestNotification,
} from '../../hooks/useNotifications'

vi.mock('../../hooks/useNotifications', () => ({
  useNotificationPreferences: vi.fn(),
  useUpdatePreferences: vi.fn(),
  useTestNotification: vi.fn(),
}))
vi.mock('./TelegramLinkCard', () => ({ TelegramLinkCard: () => null }))
vi.mock('./PushNotificationToggle', () => ({ PushNotificationToggle: () => null }))

const mutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useNotificationPreferences).mockReturnValue({
    data: { preferences: [{ channel: 'email', event_type: 'study_nudge', enabled: true }] },
    isLoading: false,
  } as never)
  vi.mocked(useUpdatePreferences).mockReturnValue({ mutate, isPending: false } as never)
  vi.mocked(useTestNotification).mockReturnValue({ mutate: vi.fn(), isPending: false } as never)
})

describe('NotificationsSection', () => {
  it('lists the day-2 study nudge and lets the user turn it off', async () => {
    const user = userEvent.setup()
    render(<NotificationsSection />)

    expect(screen.getByText('Day-2 study nudge')).toBeInTheDocument()
    const toggle = screen.getByRole('switch', { name: 'Day-2 study nudge via email' })
    expect(toggle).toHaveAttribute('aria-checked', 'true')

    await user.click(toggle)
    expect(mutate).toHaveBeenCalledWith([
      { channel: 'email', event_type: 'study_nudge', enabled: false },
    ])
  })
})

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { SendInviteForm } from './SendInviteForm'
import { useSendInvite } from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({ useSendInvite: vi.fn() }))
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

const mockSend = vi.mocked(useSendInvite)
const asResult = (q: object) => q as never
const sendMutate = vi.fn()

function result(overrides: Record<string, unknown> = {}) {
  return {
    invite: {
      id: 'inv-1',
      code: 'BETA-7F3KQ2MN',
      note: null,
      email: 'sam@example.com',
      sent_at: '2026-09-28T00:00:00Z',
      accepted_at: null,
      max_uses: 1,
      used_count: 0,
      uses_remaining: 1,
      is_redeemable: true,
      expires_at: null,
      revoked_at: null,
      created_at: '2026-09-28T00:00:00Z',
    },
    invite_url: 'https://studyaio.example/register?invite=tok123',
    email_sent: true,
    ...overrides,
  }
}

/** Drive the mutation's onSuccess as React Query would. */
function sendResolvingWith(value: ReturnType<typeof result>) {
  sendMutate.mockImplementation((_vars, opts) => opts?.onSuccess?.(value))
}

beforeEach(() => {
  vi.clearAllMocks()
  mockSend.mockReturnValue(asResult({ mutate: sendMutate, isPending: false }))
})

describe('SendInviteForm', () => {
  it('will not send without an address', () => {
    render(<SendInviteForm />)
    expect(screen.getByRole('button', { name: /send invite/i })).toBeDisabled()
  })

  it('sends the trimmed address', async () => {
    const user = userEvent.setup()
    sendResolvingWith(result())
    render(<SendInviteForm />)

    await user.type(screen.getByLabelText(/invite by email/i), '  sam@example.com  ')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(sendMutate.mock.calls[0][0]).toMatchObject({ email: 'sam@example.com' })
  })

  it('shows the link after sending', async () => {
    const user = userEvent.setup()
    sendResolvingWith(result())
    render(<SendInviteForm />)

    await user.type(screen.getByLabelText(/invite by email/i), 'sam@example.com')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(
      screen.getByText('https://studyaio.example/register?invite=tok123'),
    ).toBeInTheDocument()
  })

  it('still shows the link when the email could not be sent', async () => {
    // The load-bearing case: an instance with broken SMTP must not become one
    // where nobody can be onboarded.
    const user = userEvent.setup()
    sendResolvingWith(result({ email_sent: false }))
    render(<SendInviteForm />)

    await user.type(screen.getByLabelText(/invite by email/i), 'sam@example.com')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(screen.getByText(/could not be sent/i)).toBeInTheDocument()
    expect(
      screen.getByText('https://studyaio.example/register?invite=tok123'),
    ).toBeInTheDocument()
  })

  it('does not warn when delivery succeeded', async () => {
    const user = userEvent.setup()
    sendResolvingWith(result())
    render(<SendInviteForm />)

    await user.type(screen.getByLabelText(/invite by email/i), 'sam@example.com')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(screen.queryByText(/could not be sent/i)).not.toBeInTheDocument()
  })

  it('clears the address so the next invite cannot be sent to the last one', async () => {
    const user = userEvent.setup()
    sendResolvingWith(result())
    render(<SendInviteForm />)

    const field = screen.getByLabelText(/invite by email/i)
    await user.type(field, 'sam@example.com')
    await user.click(screen.getByRole('button', { name: /send invite/i }))

    expect(field).toHaveValue('')
  })
})

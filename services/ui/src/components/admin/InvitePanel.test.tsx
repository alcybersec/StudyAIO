import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvitePanel } from './InvitePanel'
import {
  useCreateInvite,
  useInvites,
  useResendInvite,
  useRevokeInvite,
  useSendInvite,
} from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({
  useInvites: vi.fn(),
  useCreateInvite: vi.fn(),
  useRevokeInvite: vi.fn(),
  // Used by the SendInviteForm child. Omitting it renders undefined into a
  // hook call and every test in this file fails on an unrelated error.
  useSendInvite: vi.fn(),
  useResendInvite: vi.fn(),
}))

const mockInvites = vi.mocked(useInvites)
const mockCreate = vi.mocked(useCreateInvite)
const mockRevoke = vi.mocked(useRevokeInvite)
const mockSend = vi.mocked(useSendInvite)
const mockResend = vi.mocked(useResendInvite)

const asResult = (q: object) => q as never

function invite(overrides: Record<string, unknown> = {}) {
  return {
    id: 'inv-1',
    code: 'BETA-7F3KQ2MN',
    note: 'Sam',
    email: null,
    sent_at: null,
    accepted_at: null,
    max_uses: 1,
    used_count: 0,
    uses_remaining: 1,
    is_redeemable: true,
    expires_at: '2099-01-01T00:00:00Z',
    revoked_at: null,
    created_at: '2026-09-01T00:00:00Z',
    ...overrides,
  }
}

function withInvites(invites: ReturnType<typeof invite>[]) {
  mockInvites.mockReturnValue(
    asResult({
      data: { invites, total: invites.length },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    }),
  )
}

const createMutate = vi.fn()
const revokeMutate = vi.fn()
const sendMutate = vi.fn()
const resendMutate = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  mockCreate.mockReturnValue(asResult({ mutate: createMutate, isPending: false }))
  mockRevoke.mockReturnValue(asResult({ mutate: revokeMutate, isPending: false }))
  mockSend.mockReturnValue(asResult({ mutate: sendMutate, isPending: false }))
  mockResend.mockReturnValue(asResult({ mutate: resendMutate, isPending: false }))
  withInvites([])
})

describe('InvitePanel', () => {
  it('prompts to create one when there are no codes', () => {
    render(<InvitePanel />)
    expect(screen.getByText(/no invite codes yet/i)).toBeInTheDocument()
  })

  it('lists a code with its usage', () => {
    withInvites([invite({ used_count: 1, max_uses: 3, uses_remaining: 2 })])
    render(<InvitePanel />)

    expect(screen.getByText('BETA-7F3KQ2MN')).toBeInTheDocument()
    expect(screen.getByText('1/3')).toBeInTheDocument()
    expect(screen.getByText('Sam')).toBeInTheDocument()
  })

  it('creates a code with the entered settings', async () => {
    const user = userEvent.setup()
    render(<InvitePanel />)

    await user.type(screen.getByLabelText(/note/i), 'Jordan')
    await user.clear(screen.getByLabelText(/max uses/i))
    await user.type(screen.getByLabelText(/max uses/i), '5')
    await user.click(screen.getByRole('button', { name: /create invite/i }))

    expect(createMutate).toHaveBeenCalledWith(
      { note: 'Jordan', max_uses: 5, expires_in_days: 30 },
      expect.anything(),
    )
  })

  it('revokes a code', async () => {
    withInvites([invite()])
    const user = userEvent.setup()
    render(<InvitePanel />)

    await user.click(screen.getByRole('button', { name: /revoke/i }))

    expect(revokeMutate).toHaveBeenCalledWith('inv-1', expect.anything())
  })

  it('offers no revoke button for an already-revoked code', () => {
    withInvites([invite({ revoked_at: '2026-09-02T00:00:00Z', is_redeemable: false })])
    render(<InvitePanel />)

    expect(screen.queryByRole('button', { name: /revoke/i })).not.toBeInTheDocument()
    expect(screen.getByText('revoked')).toBeInTheDocument()
  })

  it('says why a code is unusable rather than just showing inactive', () => {
    withInvites([
      invite({ id: 'a', code: 'BETA-EXPIRED1', expires_at: '2020-01-01T00:00:00Z' }),
      invite({ id: 'b', code: 'BETA-USEDUP01', used_count: 1, uses_remaining: 0 }),
    ])
    render(<InvitePanel />)

    expect(screen.getByText('expired')).toBeInTheDocument()
    expect(screen.getByText('used up')).toBeInTheDocument()
  })

  it('surfaces a load failure with a retry', () => {
    const refetch = vi.fn()
    mockInvites.mockReturnValue(
      asResult({ data: undefined, isLoading: false, isError: true, refetch }),
    )
    render(<InvitePanel />)

    expect(screen.getByText(/invite codes couldn't load/i)).toBeInTheDocument()
  })
})

describe('InvitePanel email invites', () => {
  it('distinguishes a shared code from one addressed to a person', () => {
    withInvites([invite(), invite({ id: 'inv-2', code: 'BETA-AAAA1111', email: 'sam@x.com' })])
    render(<InvitePanel />)

    expect(screen.getByText('shared code')).toBeInTheDocument()
    expect(screen.getByText('sam@x.com')).toBeInTheDocument()
  })

  it('flags an invite that was created but never delivered', () => {
    // SMTP failing looks exactly like a disinterested tester unless the two
    // are told apart in the list.
    withInvites([invite({ email: 'sam@x.com', sent_at: null })])
    render(<InvitePanel />)

    expect(screen.getByText(/not sent/i)).toBeInTheDocument()
  })

  it('does not flag one that was delivered', () => {
    withInvites([invite({ email: 'sam@x.com', sent_at: '2026-09-02T00:00:00Z' })])
    render(<InvitePanel />)

    expect(screen.queryByText(/not sent/i)).not.toBeInTheDocument()
  })
})

describe('InvitePanel resend', () => {
  const emailInvite = (o: Record<string, unknown> = {}) =>
    invite({ email: 'sam@x.com', sent_at: '2026-09-02T00:00:00Z', ...o })

  it('offers Resend for an email invite', () => {
    withInvites([emailInvite()])
    render(<InvitePanel />)
    expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument()
  })

  it('does not offer it for a shared code', () => {
    // Nowhere to send to.
    withInvites([invite()])
    render(<InvitePanel />)
    expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument()
  })

  it('does not offer it once the invite is accepted', () => {
    // The account exists; that person needs a password reset, not an invite.
    withInvites([emailInvite({ used_count: 1, max_uses: 1, uses_remaining: 0 })])
    render(<InvitePanel />)
    expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument()
  })

  it('does not offer it for a revoked invite', () => {
    withInvites([emailInvite({ revoked_at: '2026-09-03T00:00:00Z' })])
    render(<InvitePanel />)
    expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument()
  })

  it('still offers it for an expired invite', () => {
    // The usual reason to reach for the button.
    withInvites([emailInvite({ expires_at: '2020-01-01T00:00:00Z', is_redeemable: false })])
    render(<InvitePanel />)
    expect(screen.getByRole('button', { name: /resend/i })).toBeInTheDocument()
  })

  it('sends the invite id and shows the reissued link', async () => {
    const user = userEvent.setup()
    resendMutate.mockImplementation((_vars, opts) =>
      opts?.onSuccess?.({
        invite: emailInvite(),
        invite_url: 'https://studyaio.example/register?invite=new456',
        email_sent: false,
      }),
    )
    withInvites([emailInvite()])
    render(<InvitePanel />)

    await user.click(screen.getByRole('button', { name: /resend/i }))

    expect(resendMutate.mock.calls[0][0]).toMatchObject({ inviteId: 'inv-1' })
    // Delivery failed, so the link must be recoverable from the UI.
    expect(
      screen.getByText('https://studyaio.example/register?invite=new456'),
    ).toBeInTheDocument()
  })
})

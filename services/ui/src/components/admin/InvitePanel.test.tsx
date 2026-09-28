import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { InvitePanel } from './InvitePanel'
import { useCreateInvite, useInvites, useRevokeInvite, useSendInvite } from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({
  useInvites: vi.fn(),
  useCreateInvite: vi.fn(),
  useRevokeInvite: vi.fn(),
  // Used by the SendInviteForm child. Omitting it renders undefined into a
  // hook call and every test in this file fails on an unrelated error.
  useSendInvite: vi.fn(),
}))

const mockInvites = vi.mocked(useInvites)
const mockCreate = vi.mocked(useCreateInvite)
const mockRevoke = vi.mocked(useRevokeInvite)
const mockSend = vi.mocked(useSendInvite)

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

beforeEach(() => {
  vi.clearAllMocks()
  mockCreate.mockReturnValue(asResult({ mutate: createMutate, isPending: false }))
  mockRevoke.mockReturnValue(asResult({ mutate: revokeMutate, isPending: false }))
  mockSend.mockReturnValue(asResult({ mutate: sendMutate, isPending: false }))
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

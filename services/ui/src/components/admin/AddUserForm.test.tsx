import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AddUserForm } from './AddUserForm'
import { useCreateAdminUser } from '../../hooks/useApi'

vi.mock('../../hooks/useApi', () => ({ useCreateAdminUser: vi.fn() }))

const mockCreate = vi.mocked(useCreateAdminUser)
const asResult = (q: object) => q as never
const mutate = vi.fn()

const CREATED = {
  user: {
    id: 'u-new',
    email: 'tester@example.com',
    username: 'tester',
    role: 'user',
    tier: 'free',
    is_active: true,
    created_at: null,
    last_login_at: null,
  },
  setup_url: 'http://app.test/reset-password?token=abc123',
  email_sent: false,
}

beforeEach(() => {
  vi.clearAllMocks()
  mockCreate.mockReturnValue(asResult({ mutate, isPending: false }))
})

async function openAndFill() {
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /add user/i }))
  await user.type(screen.getByLabelText(/email/i), 'tester@example.com')
  await user.type(screen.getByLabelText(/username/i), 'tester')
  return user
}

describe('AddUserForm', () => {
  it('starts collapsed behind an Add user button', () => {
    render(<AddUserForm />)
    expect(screen.getByRole('button', { name: /add user/i })).toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('submits the trimmed details with defaults', async () => {
    render(<AddUserForm />)
    const user = await openAndFill()
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(mutate).toHaveBeenCalledWith(
      { email: 'tester@example.com', username: 'tester', role: 'user', tier: 'free' },
      expect.anything(),
    )
  })

  it('keeps Create disabled until the form is usable', async () => {
    render(<AddUserForm />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /add user/i }))

    const create = screen.getByRole('button', { name: /^create$/i })
    expect(create).toBeDisabled()

    await user.type(screen.getByLabelText(/email/i), 'a@b.com')
    await user.type(screen.getByLabelText(/username/i), 'ab')
    // Username under 3 characters is still not enough.
    expect(create).toBeDisabled()
  })

  it('says no password is set', async () => {
    render(<AddUserForm />)
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /add user/i }))
    expect(screen.getByText(/no password is set/i)).toBeInTheDocument()
  })

  it('shows the setup link when no email went out', async () => {
    mutate.mockImplementation((_vars, opts) => opts.onSuccess(CREATED))
    render(<AddUserForm />)
    const user = await openAndFill()
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(screen.getByText(CREATED.setup_url)).toBeInTheDocument()
    expect(screen.getByText(/send them this link yourself/i)).toBeInTheDocument()
  })

  it('says the link was emailed when it was', async () => {
    mutate.mockImplementation((_vars, opts) => opts.onSuccess({ ...CREATED, email_sent: true }))
    render(<AddUserForm />)
    const user = await openAndFill()
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(screen.getByText(/was emailed to them/i)).toBeInTheDocument()
  })

  it('warns that the link is single use and expires', async () => {
    mutate.mockImplementation((_vars, opts) => opts.onSuccess(CREATED))
    render(<AddUserForm />)
    const user = await openAndFill()
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(screen.getByText(/single use, expires in 24 hours/i)).toBeInTheDocument()
  })

  it('surfaces a server error', async () => {
    mutate.mockImplementation((_vars, opts) =>
      opts.onError(new Error('A user with this email already exists')),
    )
    render(<AddUserForm />)
    const user = await openAndFill()
    await user.click(screen.getByRole('button', { name: /^create$/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/already exists/i)
  })
})

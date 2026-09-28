import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { RegisterPage } from './RegisterPage'

const registerUser = vi.fn()
let inviteRequired = false

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    register: registerUser,
    authConfig: {
      self_hosted: false,
      registration_enabled: true,
      oauth_providers: [],
      demo_enabled: false,
      registration_mode: inviteRequired ? 'invite' : 'open',
      invite_required: inviteRequired,
    },
  }),
}))

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => navigate }
})

function setup(initialEntry = '/register') {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <RegisterPage />
    </MemoryRouter>,
  )
}

async function fillBaseFields() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText(/email/i), 'tester@example.com')
  await user.type(screen.getByLabelText(/username/i), 'tester')
  await user.type(screen.getByLabelText(/^password$/i), 'TestPass1!')
  await user.type(screen.getByLabelText(/confirm password/i), 'TestPass1!')
  return user
}

beforeEach(() => {
  registerUser.mockReset()
  registerUser.mockResolvedValue({ id: 'u1' })
  navigate.mockReset()
  inviteRequired = false
})

describe('RegisterPage — open registration', () => {
  it('does not show an invite code field', () => {
    setup()
    expect(screen.queryByLabelText(/invite code/i)).not.toBeInTheDocument()
  })

  it('registers without sending an invite code', async () => {
    setup()
    const user = await fillBaseFields()
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(registerUser).toHaveBeenCalledWith({
      email: 'tester@example.com',
      username: 'tester',
      password: 'TestPass1!',
    })
  })
})

describe('RegisterPage — invite-only registration', () => {
  beforeEach(() => {
    inviteRequired = true
  })

  it('shows the invite code field', () => {
    setup()
    expect(screen.getByLabelText(/invite code/i)).toBeInTheDocument()
  })

  it('blocks submission when the code is missing', async () => {
    setup()
    const user = await fillBaseFields()
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(registerUser).not.toHaveBeenCalled()
    expect(await screen.findByText(/invite code is required/i)).toBeInTheDocument()
  })

  it('blocks submission when the code is only whitespace', async () => {
    setup()
    const user = await fillBaseFields()
    await user.type(screen.getByLabelText(/invite code/i), '   ')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(registerUser).not.toHaveBeenCalled()
  })

  it('sends the trimmed code with the registration', async () => {
    setup()
    const user = await fillBaseFields()
    await user.type(screen.getByLabelText(/invite code/i), '  BETA-7F3KQ2MN  ')
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(registerUser).toHaveBeenCalledWith({
      email: 'tester@example.com',
      username: 'tester',
      password: 'TestPass1!',
      invite_code: 'BETA-7F3KQ2MN',
    })
  })
})

describe('RegisterPage invite links', () => {
  const TOKEN = 'aB-cD_eF12345xyzQRS'

  beforeEach(() => {
    inviteRequired = true
  })

  it('submits the token from the link without showing a code field', async () => {
    const user = userEvent.setup()
    setup(`/register?invite=${TOKEN}`)

    // The field is deliberately hidden: the visible code input carries
    // autoCapitalize="characters", which would destroy a base64url token.
    expect(screen.queryByLabelText(/invite code/i)).not.toBeInTheDocument()
    expect(screen.getByText(/signing up with an invite link/i)).toBeInTheDocument()

    await fillBaseFields()
    await user.click(screen.getByRole('button', { name: /create account/i }))

    expect(registerUser).toHaveBeenCalledWith(
      expect.objectContaining({ invite_code: TOKEN }),
    )
  })

  it('preserves the token case exactly', async () => {
    const user = userEvent.setup()
    setup(`/register?invite=${TOKEN}`)

    await fillBaseFields()
    await user.click(screen.getByRole('button', { name: /create account/i }))

    const sent = registerUser.mock.calls[0][0] as { invite_code?: string }
    // Load-bearing: uppercasing a token changes its SHA-256 and the server
    // would reject a perfectly valid invite.
    expect(sent.invite_code).toBe(TOKEN)
    expect(sent.invite_code).not.toBe(TOKEN.toUpperCase())
  })

  it('still asks for a typed code when there is no link', () => {
    setup('/register')
    expect(screen.getByLabelText(/invite code/i)).toBeInTheDocument()
    expect(screen.queryByText(/signing up with an invite link/i)).not.toBeInTheDocument()
  })
})

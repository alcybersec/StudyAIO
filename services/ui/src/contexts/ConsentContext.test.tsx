import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext, type AuthContextValue } from './AuthContext'
import { ConsentProvider } from './ConsentContext'
import { useConsent } from './consentContext'
import { api } from '../api/client'
import type { AuthUser } from '../types'

const USER: AuthUser = {
  id: 'u1',
  email: 'a@example.com',
  username: 'a',
  role: 'user',
  tier: 'free',
  is_active: true,
  email_verified: true,
  mfa_enabled: false,
  avatar_url: null,
  last_login_at: null,
  created_at: '2026-10-01T00:00:00Z',
  has_password: true,
  ai_consent_required: false,
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const CONSENT_403 = { detail: 'consent', code: 'ai_consent_required', consent_version: 3 }

function renderWith(user: AuthUser | null) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient.setQueryData(['auth', 'me'], user)
  const auth = { user } as unknown as AuthContextValue
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuthContext.Provider value={auth}>
            <ConsentProvider>
              <p>app content</p>
            </ConsentProvider>
          </AuthContext.Provider>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  }
}

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => vi.unstubAllGlobals())

describe('consent dialog from the profile', () => {
  it('stays closed when consent is not required', () => {
    renderWith(USER)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('app content')).toBeInTheDocument()
  })

  it('opens when the profile says consent is required and describes what is sent', () => {
    renderWith({ ...USER, ai_consent_required: true })
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent(/lecture files and course documents you upload, and their file names/i)
    expect(dialog).toHaveTextContent(/recent messages from the same conversation/i)
    expect(dialog).toHaveTextContent(/course codes and week numbers, and summaries the AI already wrote/i)
    expect(dialog).toHaveTextContent(/password, your email address and your username/i)
    expect(dialog).toHaveTextContent(/in its file name, is sent as is/i)
    expect(screen.getByRole('link', { name: /data & privacy/i })).toHaveAttribute('href', '/settings/privacy')
  })

  it('records consent with the shown version and closes', async () => {
    fetchMock.mockResolvedValue(json(200, { ai_consent_required: false, ai_consent_version: 2 }))
    const { queryClient } = renderWith({ ...USER, ai_consent_required: true, ai_consent_version: 2 })

    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/auth/consent')
    expect(JSON.parse(init.body)).toEqual({ version: 2 })
    expect(queryClient.getQueryData<AuthUser>(['auth', 'me'])?.ai_consent_required).toBe(false)
  })

  it('re-shows the disclosure after a 409 and reloads the profile', async () => {
    fetchMock
      .mockResolvedValueOnce(json(409, { detail: 'changed' }))
      .mockResolvedValueOnce(json(200, { ...USER, ai_consent_required: true, ai_consent_version: 4 }))
      .mockResolvedValueOnce(json(200, { ai_consent_required: false, ai_consent_version: 4 }))
    renderWith({ ...USER, ai_consent_required: true, ai_consent_version: 3 })

    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))

    expect(await screen.findByText(/disclosure was updated/i)).toBeInTheDocument()
    expect(fetchMock.mock.calls[1][0]).toBe('/api/auth/me')
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({ version: 4 })
  })

  it('keeps the dialog and says so when saving fails', async () => {
    fetchMock.mockResolvedValue(json(500, { detail: 'boom' }))
    renderWith({ ...USER, ai_consent_required: true })

    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't save your choice/i)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('"Not now" closes it without calling the server', async () => {
    renderWith({ ...USER, ai_consent_required: true })
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('app content')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('requestConsent from the UI', () => {
  function Asker({ onAnswer }: { onAnswer: (ok: boolean) => void }) {
    const { requestConsent } = useConsent()
    return <button onClick={() => void requestConsent().then(onAnswer)}>ask</button>
  }
  const renderAsker = (onAnswer: (ok: boolean) => void) => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(['auth', 'me'], USER)
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <AuthContext.Provider value={{ user: USER } as unknown as AuthContextValue}>
            <ConsentProvider>
              <Asker onAnswer={onAnswer} />
            </ConsentProvider>
          </AuthContext.Provider>
        </MemoryRouter>
      </QueryClientProvider>,
    )
  }

  it('opens the one shared dialog and resolves true after agreeing', async () => {
    fetchMock.mockResolvedValue(json(200, { ai_consent_required: false, ai_consent_version: 3 }))
    const answers: boolean[] = []
    renderAsker((ok) => answers.push(ok))
    await userEvent.click(screen.getByRole('button', { name: 'ask' }))
    expect(screen.getAllByRole('dialog')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))
    await waitFor(() => expect(answers).toEqual([true]))
  })

  it('resolves false when declined', async () => {
    const answers: boolean[] = []
    renderAsker((ok) => answers.push(ok))
    await userEvent.click(screen.getByRole('button', { name: 'ask' }))
    await userEvent.click(screen.getByRole('button', { name: 'Not now' }))
    await waitFor(() => expect(answers).toEqual([false]))
  })
})

describe('403 ai_consent_required from any request', () => {
  it('opens the dialog, then retries the original request once after consent', async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/auth/consent') return json(200, { ai_consent_required: false, ai_consent_version: 3 })
      const asked = fetchMock.mock.calls.filter(([u]) => u === '/api/qa/ask').length
      return asked === 1 ? json(403, CONSENT_403) : json(200, { answer: 'ok' })
    })
    renderWith(USER)

    const result = api.post<{ answer: string }>('/qa/ask', { q: 'hi' })
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'I agree' }))

    await expect(result).resolves.toEqual({ answer: 'ok' })
    const urls = fetchMock.mock.calls.map(([u]) => u)
    expect(urls).toEqual(['/api/qa/ask', '/api/auth/consent', '/api/qa/ask'])
    // The version comes from the 403 body: that is the wording being shown.
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ version: 3 })
  })

  it('does not retry more than once if the retry is refused again', async () => {
    fetchMock.mockImplementation(async (url: string) =>
      url === '/api/auth/consent'
        ? json(200, { ai_consent_required: false, ai_consent_version: 3 })
        : json(403, CONSENT_403),
    )
    renderWith(USER)

    const result = api.post('/qa/ask', { q: 'hi' })
    const settled = result.catch((e: Error) => e)
    await userEvent.click(await screen.findByRole('button', { name: 'I agree' }))

    expect(await settled).toMatchObject({ status: 403 })
    expect(fetchMock.mock.calls.filter(([u]) => u === '/api/qa/ask')).toHaveLength(2)
  })

  it('declining leaves the original 403 and sends nothing more', async () => {
    fetchMock.mockResolvedValue(json(403, CONSENT_403))
    renderWith(USER)

    const settled = api.post('/qa/ask', { q: 'hi' }).catch((e: Error) => e)
    await userEvent.click(await screen.findByRole('button', { name: 'Not now' }))

    expect(await settled).toMatchObject({ status: 403 })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('ignores a 403 that is not the consent gate', async () => {
    fetchMock.mockResolvedValue(json(403, { detail: 'nope' }))
    renderWith(USER)

    await expect(api.get('/anything')).rejects.toMatchObject({ status: 403 })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shares one dialog between concurrent refused requests', async () => {
    let consented = false
    fetchMock.mockImplementation(async (url: string) => {
      if (url === '/api/auth/consent') {
        consented = true
        return json(200, { ai_consent_required: false, ai_consent_version: 3 })
      }
      return consented ? json(200, { ok: url }) : json(403, CONSENT_403)
    })
    renderWith(USER)

    const a = api.get('/a')
    const b = api.get('/b')
    await userEvent.click(await screen.findByRole('button', { name: 'I agree' }))

    await expect(Promise.all([a, b])).resolves.toEqual([{ ok: '/api/a' }, { ok: '/api/b' }])
    expect(fetchMock.mock.calls.filter(([u]) => u === '/api/auth/consent')).toHaveLength(1)
  })
})

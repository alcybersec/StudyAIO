import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AiProvidersSection } from './AiProvidersSection'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'
import { useAuth } from '../../../hooks/useAuth'
import type { Settings } from '../../../types'

vi.mock('../../../hooks/useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

vi.mock('../../../hooks/useAuth', () => ({ useAuth: vi.fn() }))

vi.mock('../../../api/endpoints', () => ({
  settingsApi: { testAi: vi.fn() },
}))

const mockSettings = vi.mocked(useSettings)
const mockUpdate = vi.mocked(useUpdateSettings)
const mockAuth = vi.mocked(useAuth)
const asHosted = (selfHosted: boolean) =>
  mockAuth.mockReturnValue({ isSelfHosted: selfHosted } as never)
const asResult = (q: object) => q as never
const mutate = vi.fn()

function settings(overrides: Partial<Settings> = {}): Settings {
  return {
    claude_code_path: 'claude',
    claude_model: 'sonnet',
    agent_backend: 'studyaio',
    anthropic_api_key_configured: false,
    claude_cli_credentials_configured: false,
    openai_api_key_configured: false,
    zai_api_key_configured: false,
    openai_model: '',
    zai_model: '',
    zai_base_url: '',
    ollama_base_url: '',
    ollama_model: '',
    classification_confidence_threshold: 0.7,
    flashcard_count_per_week: 15,
    quiz_question_count_per_week: 8,
    chunk_size_tokens: 500,
    chunk_overlap_tokens: 50,
    language: 'en',
    content_language: false,
    leaderboard_opt_in: false,
    dashboard_layout: null,
    timezone: 'UTC',
    ...overrides,
  }
}

function withSettings(overrides: Partial<Settings> = {}) {
  mockSettings.mockReturnValue(
    asResult({ data: settings(overrides), isLoading: false, error: null, refetch: vi.fn() }),
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
  asHosted(false)
  withSettings()
})

describe('AiProvidersSection', () => {
  it('defaults to StudyAIO provided with no credential fields', () => {
    withSettings()
    render(<AiProvidersSection />)

    expect(screen.getByRole('button', { name: /StudyAIO provided/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/CLI credentials/)).not.toBeInTheDocument()
  })

  it('reveals an empty credential field, marked not set, for a chosen provider', async () => {
    const user = userEvent.setup()
    withSettings({ agent_backend: 'studyaio' })
    render(<AiProvidersSection />)

    await user.click(screen.getByRole('button', { name: /Z\.ai/ }))

    const field = screen.getByLabelText(/API key/)
    expect(field).toHaveValue('')
    expect(screen.getByText('not set')).toBeInTheDocument()
    expect(mutate).toHaveBeenCalledWith({ agent_backend: 'zai' }, expect.anything())
  })

  it('shows a configured credential as configured, never as a value', () => {
    withSettings({ agent_backend: 'zai', zai_api_key_configured: true })
    render(<AiProvidersSection />)

    expect(screen.getByLabelText(/API key/)).toHaveValue('')
    expect(screen.getByText('configured')).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Leave blank to keep the stored key/)).toBeInTheDocument()
  })

  it('removes a stored credential only when explicitly asked', async () => {
    const user = userEvent.setup()
    withSettings({ agent_backend: 'zai', zai_api_key_configured: true })
    render(<AiProvidersSection />)

    await user.click(screen.getByRole('button', { name: /Remove/ }))

    expect(mutate).toHaveBeenCalledWith({ clear_secrets: ['zai_api_key'] }, expect.anything())
  })

  it('offers no Remove control when nothing is stored', () => {
    withSettings({ agent_backend: 'zai' })
    render(<AiProvidersSection />)

    expect(screen.queryByRole('button', { name: /Remove/ })).not.toBeInTheDocument()
  })

  it('shows the Claude CLI path and model read-only, set by the operator', () => {
    withSettings({ agent_backend: 'claude_code', claude_code_path: '/opt/claude', claude_model: 'opus' })
    render(<AiProvidersSection />)

    expect(screen.queryByRole('textbox', { name: /Claude CLI path/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(screen.getByText('/opt/claude')).toBeInTheDocument()
    expect(screen.getByText('opus')).toBeInTheDocument()
    expect(screen.getAllByText('Set by the server operator')).toHaveLength(2)
  })

  it('makes the Ollama provider unavailable when not self-hosted', async () => {
    const user = userEvent.setup()
    render(<AiProvidersSection />)

    const ollama = screen.getByRole('button', { name: /Ollama/ })
    expect(ollama).toBeDisabled()
    expect(screen.getByText(/Not available on this server/)).toBeInTheDocument()
    await user.click(ollama)
    expect(mutate).not.toHaveBeenCalled()
  })

  it('lets a self-hosted user pick Ollama and edit its base URL', () => {
    asHosted(true)
    withSettings({ agent_backend: 'ollama' })
    render(<AiProvidersSection />)

    expect(screen.getByRole('button', { name: /Ollama/ })).toBeEnabled()
    expect(screen.getByRole('textbox', { name: 'Base URL' })).toBeInTheDocument()
  })

  it('shows the Z.ai endpoint read-only when not self-hosted, editable when self-hosted', () => {
    withSettings({ agent_backend: 'zai', zai_base_url: 'https://ops.example/v4/' })
    const { unmount } = render(<AiProvidersSection />)
    expect(screen.queryByRole('textbox', { name: 'Endpoint' })).not.toBeInTheDocument()
    expect(screen.getByText('https://ops.example/v4/')).toBeInTheDocument()
    unmount()

    asHosted(true)
    render(<AiProvidersSection />)
    expect(screen.getByRole('textbox', { name: 'Endpoint' })).toBeInTheDocument()
  })
})

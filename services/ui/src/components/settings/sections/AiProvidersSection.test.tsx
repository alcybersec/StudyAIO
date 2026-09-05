import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AiProvidersSection } from './AiProvidersSection'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'
import type { Settings } from '../../../types'

vi.mock('../../../hooks/useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

vi.mock('../../../api/endpoints', () => ({
  settingsApi: { testAi: vi.fn() },
}))

const mockSettings = vi.mocked(useSettings)
const mockUpdate = vi.mocked(useUpdateSettings)
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
    dashboard_layout: null,
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
})

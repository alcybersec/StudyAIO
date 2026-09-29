import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AppearanceSection } from './AppearanceSection'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'
import type { Settings } from '../../../types'
import i18n from '../../../i18n'

vi.mock('../../../hooks/useApi', () => ({
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
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
    language: 'en',
    content_language: false,
    dashboard_layout: null,
    ...overrides,
  }
}

function withSettings(overrides: Partial<Settings> = {}) {
  mockSettings.mockReturnValue(asResult({ data: settings(overrides), isLoading: false }))
}

beforeEach(async () => {
  vi.clearAllMocks()
  mockUpdate.mockReturnValue(asResult({ mutate, isPending: false }))
  withSettings()
  await i18n.changeLanguage('en')
})

describe('AppearanceSection language control', () => {
  it('shows the stored language as selected', () => {
    withSettings({ language: 'ru' })
    render(<AppearanceSection />)

    expect(screen.getByRole('button', { name: 'Русский' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'English' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('persists a chosen language through the settings mutation', async () => {
    const user = userEvent.setup()
    render(<AppearanceSection />)

    await user.click(screen.getByRole('button', { name: 'Русский' }))

    expect(mutate).toHaveBeenCalledWith({ language: 'ru' })
  })

  it('adopts the stored language and renders in it', async () => {
    // The server is authoritative: the setting follows the account to another
    // browser, where localStorage knows nothing.
    withSettings({ language: 'ru' })
    render(<AppearanceSection />)

    await waitFor(() => expect(screen.getByText('Внешний вид')).toBeInTheDocument())
    expect(document.documentElement.lang).toBe('ru')
  })

  it('names each language in its own language', () => {
    render(<AppearanceSection />)

    // Not "Russian": someone looking for their language reads it in theirs.
    expect(screen.getByRole('button', { name: 'Русский' })).toBeInTheDocument()
  })

  describe('content toggle', () => {
    const toggle = () => screen.getByRole('checkbox')

    it('is disabled while the language is English', () => {
      // "Also generate content in English" is the existing behaviour, so
      // offering it would imply a choice that does nothing.
      render(<AppearanceSection />)

      expect(toggle()).toBeDisabled()
      expect(screen.getByText(/Available once you choose a language other than English/)).toBeInTheDocument()
    })

    it('is available once another language is chosen', () => {
      withSettings({ language: 'ru' })
      render(<AppearanceSection />)

      expect(toggle()).toBeEnabled()
    })

    it('reflects the stored value', () => {
      withSettings({ language: 'ru', content_language: true })
      render(<AppearanceSection />)

      expect(toggle()).toBeChecked()
    })

    it('persists through the settings mutation', async () => {
      const user = userEvent.setup()
      withSettings({ language: 'ru' })
      render(<AppearanceSection />)

      await user.click(toggle())

      expect(mutate).toHaveBeenCalledWith({ content_language: true })
    })

    it('stays off by default, so shipping this changes nobody’s output', () => {
      withSettings({ language: 'ru' })
      render(<AppearanceSection />)

      expect(toggle()).not.toBeChecked()
    })
  })
})

import { describe, expect, it } from 'vitest'
import {
  aiProviderSettingsSchema,
  forgotPasswordSchema,
  loginSchema,
  pipelineSettingsSchema,
  registerSchema,
  resetPasswordSchema,
} from './schemas'

const validAiSettings = {
  agent_backend: 'claude_code',
  claude_code_path: '/usr/local/bin/claude',
  claude_model: 'sonnet',
  claude_cli_credentials: '',
  anthropic_api_key: '',
  openai_api_key: '',
  openai_model: 'gpt-4o',
  zai_api_key: '',
  zai_model: 'glm-5.3',
  zai_base_url: '',
  ollama_base_url: 'http://ollama:11434',
  ollama_model: 'llama3.2',
  embedding_backend: 'sentence_transformers',
  classification_confidence_threshold: 0.75,
}

describe('aiProviderSettingsSchema', () => {
  it('accepts a valid settings shape', () => {
    expect(aiProviderSettingsSchema.safeParse(validAiSettings).success).toBe(true)
  })

  it('rejects an Anthropic key without the sk-ant- prefix', () => {
    const result = aiProviderSettingsSchema.safeParse({
      ...validAiSettings,
      anthropic_api_key: 'sk-live-0f3a9c',
    })
    expect(result.success).toBe(false)
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === 'anthropic_api_key')
      expect(issue?.message).toMatch(/sk-ant-/)
    }
  })

  it('accepts an empty Anthropic key (unset) and a proper sk-ant- key', () => {
    expect(
      aiProviderSettingsSchema.safeParse({ ...validAiSettings, anthropic_api_key: '' }).success,
    ).toBe(true)
    expect(
      aiProviderSettingsSchema.safeParse({ ...validAiSettings, anthropic_api_key: 'sk-ant-abc123' })
        .success,
    ).toBe(true)
  })

  it('rejects an OpenAI key without the sk- prefix', () => {
    const result = aiProviderSettingsSchema.safeParse({
      ...validAiSettings,
      openai_api_key: 'not-a-key',
    })
    expect(result.success).toBe(false)
  })

  it('rejects a non-URL Ollama base URL', () => {
    const result = aiProviderSettingsSchema.safeParse({
      ...validAiSettings,
      ollama_base_url: 'localhost:11434',
    })
    expect(result.success).toBe(false)
  })

  it('rejects a confidence threshold above 1', () => {
    const result = aiProviderSettingsSchema.safeParse({
      ...validAiSettings,
      classification_confidence_threshold: 1.5,
    })
    expect(result.success).toBe(false)
  })
})

describe('pipelineSettingsSchema', () => {
  const valid = {
    flashcard_count_per_week: 20,
    quiz_question_count_per_week: 10,
    chunk_size_tokens: 500,
    chunk_overlap_tokens: 50,
  }

  it('accepts values within bounds', () => {
    expect(pipelineSettingsSchema.safeParse(valid).success).toBe(true)
  })

  it('rejects out-of-range values', () => {
    expect(
      pipelineSettingsSchema.safeParse({ ...valid, flashcard_count_per_week: 0 }).success,
    ).toBe(false)
    expect(pipelineSettingsSchema.safeParse({ ...valid, chunk_size_tokens: 10 }).success).toBe(
      false,
    )
    expect(
      pipelineSettingsSchema.safeParse({ ...valid, chunk_overlap_tokens: 600 }).success,
    ).toBe(false)
  })
})

describe('auth schemas', () => {
  it('loginSchema requires a valid email and a password', () => {
    expect(loginSchema.safeParse({ email: 'a@b.co', password: 'x' }).success).toBe(true)
    expect(loginSchema.safeParse({ email: 'nope', password: 'x' }).success).toBe(false)
    expect(loginSchema.safeParse({ email: 'a@b.co', password: '' }).success).toBe(false)
  })

  it('registerSchema enforces password length and confirmation match', () => {
    const base = { email: 'a@b.co', username: 'alex' }
    expect(
      registerSchema.safeParse({ ...base, password: 'longenough', confirm: 'longenough' }).success,
    ).toBe(true)
    expect(
      registerSchema.safeParse({ ...base, password: 'short', confirm: 'short' }).success,
    ).toBe(false)

    const mismatch = registerSchema.safeParse({
      ...base,
      password: 'longenough',
      confirm: 'different1',
    })
    expect(mismatch.success).toBe(false)
    if (!mismatch.success) {
      expect(mismatch.error.issues.some((i) => i.path[0] === 'confirm')).toBe(true)
    }
  })

  it('forgotPasswordSchema validates the email format', () => {
    expect(forgotPasswordSchema.safeParse({ email: 'a@b.co' }).success).toBe(true)
    expect(forgotPasswordSchema.safeParse({ email: 'bad' }).success).toBe(false)
  })

  it('resetPasswordSchema mirrors the register password rules', () => {
    expect(
      resetPasswordSchema.safeParse({ password: 'longenough', confirm: 'longenough' }).success,
    ).toBe(true)
    expect(
      resetPasswordSchema.safeParse({ password: 'longenough', confirm: 'other12345' }).success,
    ).toBe(false)
  })
})

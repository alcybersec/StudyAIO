import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Globe, Server, Sparkles, Terminal, type LucideIcon } from 'lucide-react'
import { Badge, Button, Card, ErrorState, Input, Select, SkeletonCard, Textarea } from '../../ui'
import { FieldSavedNote } from '../FieldSavedNote'
import { useSavedFields } from '../useSavedFields'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'
import { settingsApi } from '../../../api/endpoints'
import { toastMutationError } from '../../../lib/toast'
import {
  AGENT_BACKENDS,
  aiProviderSettingsSchema,
  type AiProviderSettingsFormData,
} from '../../../lib/schemas'
import type { Settings } from '../../../types'

type AgentBackend = (typeof AGENT_BACKENDS)[number]

interface ProviderMeta {
  id: AgentBackend
  name: string
  icon: LucideIcon
  desc: string
  status: (s: Settings) => { text: string; ok: boolean }
}

const PROVIDERS: ProviderMeta[] = [
  {
    id: 'claude_code',
    name: 'Claude Code CLI',
    icon: Terminal,
    desc: 'Uses your Max plan via the local CLI — no API key needed.',
    status: (s) =>
      s.claude_cli_credentials?.trim()
        ? { text: 'own CLI credentials configured', ok: true }
        : { text: 'using system default credentials', ok: true },
  },
  {
    id: 'anthropic_api',
    name: 'Anthropic API',
    icon: Sparkles,
    desc: 'Direct API access with your own key. Pay per token.',
    status: (s) =>
      s.anthropic_api_key
        ? { text: 'key configured', ok: true }
        : { text: 'no key configured', ok: false },
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: Globe,
    desc: 'GPT models for summaries, flashcards and Q&A.',
    status: (s) =>
      s.openai_api_key
        ? { text: 'key configured', ok: true }
        : { text: 'no key configured', ok: false },
  },
  {
    id: 'ollama',
    name: 'Ollama',
    icon: Server,
    desc: 'Local models — private, free, slower on big lectures.',
    status: (s) => ({ text: `at ${s.ollama_base_url || 'http://ollama:11434'}`, ok: true }),
  },
]

const CLAUDE_MODEL_OPTIONS = [
  { value: 'opus', label: 'Opus' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'haiku', label: 'Haiku' },
]

const EMBEDDING_OPTIONS = [
  { value: 'sentence_transformers', label: 'Sentence Transformers (Local)' },
  { value: 'openai', label: 'OpenAI Embeddings' },
  { value: 'ollama', label: 'Ollama Embeddings' },
]

const PROVIDER_TITLES: Record<AgentBackend, string> = {
  claude_code: 'Claude Code CLI configuration',
  anthropic_api: 'Anthropic API configuration',
  openai: 'OpenAI configuration',
  ollama: 'Ollama configuration',
}

function toFormValues(s: Settings): AiProviderSettingsFormData {
  const backend = (AGENT_BACKENDS as readonly string[]).includes(s.agent_backend)
    ? (s.agent_backend as AgentBackend)
    : 'claude_code'
  const embedding = ['sentence_transformers', 'openai', 'ollama'].includes(s.embedding_backend)
    ? (s.embedding_backend as AiProviderSettingsFormData['embedding_backend'])
    : 'sentence_transformers'
  return {
    agent_backend: backend,
    claude_code_path: s.claude_code_path ?? '',
    claude_model: s.claude_model ?? 'sonnet',
    claude_cli_credentials: s.claude_cli_credentials ?? '',
    anthropic_api_key: s.anthropic_api_key ?? '',
    openai_api_key: s.openai_api_key ?? '',
    openai_model: s.openai_model ?? '',
    ollama_base_url: s.ollama_base_url ?? '',
    ollama_model: s.ollama_model ?? '',
    embedding_backend: embedding,
    classification_confidence_threshold: s.classification_confidence_threshold ?? 0.7,
  }
}

interface LabelRowProps {
  htmlFor: string
  label: string
  saved: boolean
}

function LabelRow({ htmlFor, label, saved }: LabelRowProps) {
  return (
    <div className="flex items-center justify-between mb-1.5">
      <label htmlFor={htmlFor} className="text-xs font-medium text-text-muted">
        {label}
      </label>
      <FieldSavedNote show={saved} />
    </div>
  )
}

export function AiProvidersSection() {
  const { data: settings, isLoading, error, refetch } = useSettings()

  if (isLoading) return <SkeletonCard />
  if (error) {
    return (
      <ErrorState
        title="AI provider settings couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!settings) return null

  return <AiProvidersForm settings={settings} />
}

function AiProvidersForm({ settings }: { settings: Settings }) {
  const updateMutation = useUpdateSettings()
  const { saved, markSaved } = useSavedFields()
  const [test, setTest] = useState<{ state: 'idle' | 'testing' | 'ok' | 'error'; message?: string }>(
    { state: 'idle' },
  )

  const {
    register,
    getValues,
    setValue,
    trigger,
    watch,
    formState: { errors },
  } = useForm<AiProviderSettingsFormData>({
    resolver: zodResolver(aiProviderSettingsSchema),
    mode: 'onBlur',
    values: toFormValues(settings),
    resetOptions: { keepDirtyValues: true },
  })

  const backend = watch('agent_backend')

  const saveValue = (field: keyof AiProviderSettingsFormData, value: unknown) => {
    updateMutation.mutate(
      { [field]: value } as Partial<Settings>,
      {
        onSuccess: () => markSaved(field),
        onError: (err) => toastMutationError(err),
      },
    )
  }

  /** Validate a field on blur and persist it if it changed. */
  const saveField = async (field: keyof AiProviderSettingsFormData) => {
    const valid = await trigger(field)
    if (!valid) return
    const value = getValues(field)
    const server = toFormValues(settings)
    if (server[field] === value) return
    saveValue(field, value)
  }

  const selectProvider = (id: AgentBackend) => {
    if (id === backend) return
    setValue('agent_backend', id)
    saveValue('agent_backend', id)
  }

  const selectField = (field: 'claude_model' | 'embedding_backend') => (value: string) => {
    if (getValues(field) === value) return
    setValue(field, value as never)
    saveValue(field, value)
  }

  const runTest = async () => {
    setTest({ state: 'testing' })
    const started = Date.now()
    try {
      const result = await settingsApi.testAi()
      const secs = ((Date.now() - started) / 1000).toFixed(1)
      setTest({ state: 'ok', message: `✓ ${result.backend} responded in ${secs}s` })
    } catch (err) {
      setTest({
        state: 'error',
        message: err instanceof Error ? err.message : 'Connection test failed',
      })
    }
  }

  const registerWithSave = (field: keyof AiProviderSettingsFormData, valueAsNumber = false) =>
    register(field, { onBlur: () => saveField(field), valueAsNumber })

  return (
    <div>
      <h2 className="text-[13px] font-semibold text-text mb-1">AI Providers</h2>
      <p className="text-xs text-text-muted mb-4 max-w-lg">
        One provider handles everything — summaries, flashcards, Q&amp;A. Switch anytime; nothing
        already generated is lost.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {PROVIDERS.map((provider) => {
          const Icon = provider.icon
          const selected = backend === provider.id
          const status = provider.status(settings)
          return (
            <button
              key={provider.id}
              type="button"
              onClick={() => selectProvider(provider.id)}
              aria-pressed={selected}
              className={`text-left rounded-xl border p-3 transition-colors cursor-pointer ${
                selected
                  ? 'border-sage ring-1 ring-sage bg-sage-soft/40'
                  : 'border-border bg-surface-1 hover:border-border-strong'
              }`}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 text-[13px] font-semibold text-text">
                  <Icon size={14} className={selected ? 'text-sage-fg' : 'text-text-faint'} aria-hidden />
                  {provider.name}
                </span>
                {selected && <Badge variant="success">active</Badge>}
              </span>
              <span className="block text-xs text-text-muted mt-1.5">{provider.desc}</span>
              <span
                className={`block text-[11px] font-mono mt-2 ${status.ok ? 'text-sage-fg' : 'text-text-faint'}`}
              >
                {status.text}
              </span>
            </button>
          )
        })}
      </div>

      <Card className="mt-5">
        <div className="text-[13px] font-semibold text-text mb-4">{PROVIDER_TITLES[backend]}</div>

        <div className="space-y-4 max-w-md">
          {backend === 'claude_code' && (
            <>
              <div>
                <LabelRow htmlFor="claude_code_path" label="Claude CLI path" saved={!!saved.claude_code_path} />
                <Input
                  id="claude_code_path"
                  className="font-mono"
                  error={errors.claude_code_path?.message}
                  {...registerWithSave('claude_code_path')}
                />
              </div>
              <div>
                <LabelRow htmlFor="claude_model" label="Model" saved={!!saved.claude_model} />
                <Select
                  id="claude_model"
                  options={CLAUDE_MODEL_OPTIONS}
                  value={watch('claude_model')}
                  onValueChange={selectField('claude_model')}
                />
              </div>
              <div>
                <LabelRow
                  htmlFor="claude_cli_credentials"
                  label={
                    settings.claude_cli_credentials?.trim()
                      ? 'CLI credentials — configured'
                      : 'CLI credentials — using system default'
                  }
                  saved={!!saved.claude_cli_credentials}
                />
                <Textarea
                  id="claude_cli_credentials"
                  rows={4}
                  className="font-mono text-xs"
                  placeholder="Paste contents of ~/.claude/.credentials.json"
                  error={errors.claude_cli_credentials?.message}
                  {...registerWithSave('claude_cli_credentials')}
                />
                <p className="mt-1.5 text-xs text-text-faint">
                  To use your own Max subscription: run{' '}
                  <code className="px-1 py-0.5 bg-surface-2 rounded text-[11px]">claude login</code> on
                  your computer, then paste the contents of{' '}
                  <code className="px-1 py-0.5 bg-surface-2 rounded text-[11px]">
                    ~/.claude/.credentials.json
                  </code>
                  . Leave empty to use the system default.
                </p>
              </div>
            </>
          )}

          {backend === 'anthropic_api' && (
            <>
              <div>
                <LabelRow htmlFor="anthropic_api_key" label="API key" saved={!!saved.anthropic_api_key} />
                <Input
                  id="anthropic_api_key"
                  type="password"
                  placeholder="sk-ant-…"
                  className="font-mono"
                  autoComplete="off"
                  error={errors.anthropic_api_key?.message}
                  {...registerWithSave('anthropic_api_key')}
                />
              </div>
              <div>
                <LabelRow htmlFor="claude_model_api" label="Model" saved={!!saved.claude_model} />
                <Select
                  id="claude_model_api"
                  options={CLAUDE_MODEL_OPTIONS}
                  value={watch('claude_model')}
                  onValueChange={selectField('claude_model')}
                />
              </div>
            </>
          )}

          {backend === 'openai' && (
            <>
              <div>
                <LabelRow htmlFor="openai_api_key" label="API key" saved={!!saved.openai_api_key} />
                <Input
                  id="openai_api_key"
                  type="password"
                  placeholder="sk-…"
                  className="font-mono"
                  autoComplete="off"
                  error={errors.openai_api_key?.message}
                  {...registerWithSave('openai_api_key')}
                />
              </div>
              <div>
                <LabelRow htmlFor="openai_model" label="Model" saved={!!saved.openai_model} />
                <Input
                  id="openai_model"
                  placeholder="gpt-4o"
                  className="font-mono"
                  error={errors.openai_model?.message}
                  {...registerWithSave('openai_model')}
                />
                <p className="mt-1.5 text-xs text-text-faint">e.g. gpt-4o, gpt-4o-mini, o1</p>
              </div>
            </>
          )}

          {backend === 'ollama' && (
            <>
              <div>
                <LabelRow htmlFor="ollama_base_url" label="Base URL" saved={!!saved.ollama_base_url} />
                <Input
                  id="ollama_base_url"
                  placeholder="http://ollama:11434"
                  className="font-mono"
                  error={errors.ollama_base_url?.message}
                  {...registerWithSave('ollama_base_url')}
                />
              </div>
              <div>
                <LabelRow htmlFor="ollama_model" label="Model" saved={!!saved.ollama_model} />
                <Input
                  id="ollama_model"
                  placeholder="llama3.2"
                  className="font-mono"
                  error={errors.ollama_model?.message}
                  {...registerWithSave('ollama_model')}
                />
                <p className="mt-1.5 text-xs text-text-faint">Model name as shown in `ollama list`</p>
              </div>
            </>
          )}

          <div className="flex items-center gap-3 pt-1">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={test.state === 'testing'}
              onClick={runTest}
            >
              {test.state === 'testing' ? 'Testing…' : 'Test connection'}
            </Button>
            {test.state === 'ok' && (
              <span className="text-xs text-sage-fg" role="status">
                {test.message}
              </span>
            )}
            {test.state === 'error' && (
              <span className="text-xs text-red-fg" role="status">
                {test.message}
              </span>
            )}
          </div>
        </div>
      </Card>

      <Card className="mt-4">
        <div className="text-[13px] font-semibold text-text mb-4">Shared AI behavior</div>
        <div className="space-y-4 max-w-md">
          <div>
            <LabelRow
              htmlFor="classification_confidence_threshold"
              label="Classification confidence threshold"
              saved={!!saved.classification_confidence_threshold}
            />
            <Input
              id="classification_confidence_threshold"
              type="number"
              min={0}
              max={1}
              step={0.05}
              error={errors.classification_confidence_threshold?.message}
              {...registerWithSave('classification_confidence_threshold', true)}
            />
            <p className="mt-1.5 text-xs text-text-faint">
              Below this threshold, classifications go to review (0.0 – 1.0)
            </p>
          </div>
          <div>
            <LabelRow
              htmlFor="embedding_backend"
              label="Embedding backend"
              saved={!!saved.embedding_backend}
            />
            <Select
              id="embedding_backend"
              options={EMBEDDING_OPTIONS}
              value={watch('embedding_backend')}
              onValueChange={selectField('embedding_backend')}
            />
            <p className="mt-1.5 text-xs text-text-faint">
              Backend used for generating text embeddings for similarity search
            </p>
          </div>
        </div>
      </Card>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
        <span className="text-xs text-text-faint">Changes save automatically</span>
      </div>
    </div>
  )
}

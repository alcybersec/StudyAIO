import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Cpu, Globe, Server, Sparkles, Terminal, Zap, type LucideIcon } from 'lucide-react'
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
import type { Settings, SettingsUpdate } from '../../../types'

type AgentBackend = (typeof AGENT_BACKENDS)[number]

interface ProviderMeta {
  id: AgentBackend
  name: string
  icon: LucideIcon
  desc: string
  status: (s: Settings) => { text: string; ok: boolean }
}

const NOT_SET = { text: 'your key is not set', ok: false }

const PROVIDERS: ProviderMeta[] = [
  {
    id: 'studyaio',
    name: 'StudyAIO provided',
    icon: Zap,
    desc: 'Included with your account. Nothing to configure, no key of your own.',
    status: () => ({ text: 'included — no key needed', ok: true }),
  },
  {
    id: 'claude_code',
    name: 'Claude Code CLI',
    icon: Terminal,
    desc: 'Your own Max plan, via CLI credentials you paste in.',
    status: (s) =>
      s.claude_cli_credentials_configured
        ? { text: 'your CLI credentials are set', ok: true }
        : { text: 'your credentials are not set', ok: false },
  },
  {
    id: 'anthropic_api',
    name: 'Anthropic API',
    icon: Sparkles,
    desc: 'Direct API access with your own key. You pay per token.',
    status: (s) => (s.anthropic_api_key_configured ? { text: 'your key is set', ok: true } : NOT_SET),
  },
  {
    id: 'openai',
    name: 'OpenAI',
    icon: Globe,
    desc: 'GPT models with your own key. You pay per token.',
    status: (s) => (s.openai_api_key_configured ? { text: 'your key is set', ok: true } : NOT_SET),
  },
  {
    id: 'zai',
    name: 'Z.ai',
    icon: Cpu,
    desc: 'GLM models via Z.ai with your own key — OpenAI-compatible.',
    status: (s) =>
      s.zai_api_key_configured
        ? { text: `your key is set (${s.zai_model || 'glm-5.3'})`, ok: true }
        : NOT_SET,
  },
  {
    id: 'ollama',
    name: 'Ollama',
    icon: Server,
    desc: 'Your own Ollama server — private, free, slower on big lectures.',
    status: (s) =>
      s.ollama_base_url
        ? { text: `at ${s.ollama_base_url}`, ok: true }
        : { text: 'your endpoint is not set', ok: false },
  },
]

const CLAUDE_MODEL_OPTIONS = [
  { value: 'opus', label: 'Opus' },
  { value: 'sonnet', label: 'Sonnet' },
  { value: 'haiku', label: 'Haiku' },
]

const PROVIDER_TITLES: Record<AgentBackend, string> = {
  studyaio: 'StudyAIO provided',
  claude_code: 'Claude Code CLI configuration',
  anthropic_api: 'Anthropic API configuration',
  openai: 'OpenAI configuration',
  zai: 'Z.ai configuration',
  ollama: 'Ollama configuration',
}

/**
 * Map the server's settings onto form values.
 *
 * Credential fields are always blank: the server never sends a value, and a
 * blank submission means "leave the stored one unchanged". A credential
 * therefore never round-trips through here.
 */
function toFormValues(s: Settings): AiProviderSettingsFormData {
  const backend = (AGENT_BACKENDS as readonly string[]).includes(s.agent_backend)
    ? (s.agent_backend as AgentBackend)
    : 'studyaio'
  return {
    agent_backend: backend,
    claude_code_path: s.claude_code_path ?? '',
    claude_model: s.claude_model ?? 'sonnet',
    claude_cli_credentials: '',
    anthropic_api_key: '',
    openai_api_key: '',
    openai_model: s.openai_model ?? '',
    zai_api_key: '',
    zai_model: s.zai_model ?? '',
    zai_base_url: s.zai_base_url ?? '',
    ollama_base_url: s.ollama_base_url ?? '',
    ollama_model: s.ollama_model ?? '',
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

/** Write-only fields: the server reports whether one is stored, never its value. */
type SecretField =
  | 'anthropic_api_key'
  | 'openai_api_key'
  | 'zai_api_key'
  | 'claude_cli_credentials'

interface SecretLabelRowProps {
  htmlFor: string
  label: string
  saved: boolean
  configured: boolean
  onClear: () => void
}

/** Label for a write-only credential: says whether one is stored, never what. */
function SecretLabelRow({ htmlFor, label, saved, configured, onClear }: SecretLabelRowProps) {
  return (
    <div className="flex items-center justify-between gap-2 mb-1.5">
      <label htmlFor={htmlFor} className="text-xs font-medium text-text-muted">
        {label} —{' '}
        <span className={configured ? 'text-sage-fg' : 'text-text-faint'}>
          {configured ? 'configured' : 'not set'}
        </span>
      </label>
      <span className="flex items-center gap-2">
        <FieldSavedNote show={saved} />
        {configured && (
          <button
            type="button"
            onClick={onClear}
            className="text-[11px] text-text-faint hover:text-red-fg underline cursor-pointer"
          >
            Remove
          </button>
        )}
      </span>
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
    updateMutation.mutate({ [field]: value } as SettingsUpdate, {
      onSuccess: () => markSaved(field),
      onError: (err) => toastMutationError(err),
    })
  }

  /**
   * Delete a stored credential.
   *
   * Submitting an empty field means "unchanged", so removal has to be said
   * out loud — otherwise there would be no way back to having no key at all.
   */
  const clearSecret = (field: SecretField) => {
    updateMutation.mutate({ clear_secrets: [field] }, {
      onSuccess: () => {
        setValue(field, '')
        markSaved(field)
      },
      onError: (err) => toastMutationError(err),
    })
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

  const selectField = (field: 'claude_model') => (value: string) => {
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
      // The instance reports itself as `studyaio` — it does not name which
      // provider the operator pays for, and neither do we.
      const label = result.backend === 'studyaio' ? 'StudyAIO' : result.backend
      setTest({ state: 'ok', message: `✓ ${label} responded in ${secs}s` })
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
          {backend === 'studyaio' && (
            <p className="text-xs text-text-muted">
              StudyAIO runs the AI for you on its own provider account. There is nothing to set
              up and no key to paste. Pick another provider above only if you want your work to
              run on your own account and your own bill.
            </p>
          )}

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
                <SecretLabelRow
                  htmlFor="claude_cli_credentials"
                  label="CLI credentials"
                  saved={!!saved.claude_cli_credentials}
                  configured={settings.claude_cli_credentials_configured}
                  onClear={() => clearSecret('claude_cli_credentials')}
                />
                <Textarea
                  id="claude_cli_credentials"
                  rows={4}
                  className="font-mono text-xs"
                  placeholder={
                    settings.claude_cli_credentials_configured
                      ? 'Leave blank to keep the stored credentials'
                      : 'Paste contents of ~/.claude/.credentials.json'
                  }
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
                  . Leaving this blank keeps whatever is already stored.
                </p>
              </div>
            </>
          )}

          {backend === 'anthropic_api' && (
            <>
              <div>
                <SecretLabelRow
                  htmlFor="anthropic_api_key"
                  label="API key"
                  saved={!!saved.anthropic_api_key}
                  configured={settings.anthropic_api_key_configured}
                  onClear={() => clearSecret('anthropic_api_key')}
                />
                <Input
                  id="anthropic_api_key"
                  type="password"
                  placeholder={
                    settings.anthropic_api_key_configured
                      ? 'Leave blank to keep the stored key'
                      : 'sk-ant-…'
                  }
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
                <SecretLabelRow
                  htmlFor="openai_api_key"
                  label="API key"
                  saved={!!saved.openai_api_key}
                  configured={settings.openai_api_key_configured}
                  onClear={() => clearSecret('openai_api_key')}
                />
                <Input
                  id="openai_api_key"
                  type="password"
                  placeholder={
                    settings.openai_api_key_configured
                      ? 'Leave blank to keep the stored key'
                      : 'sk-…'
                  }
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

          {backend === 'zai' && (
            <>
              <div>
                <SecretLabelRow
                  htmlFor="zai_api_key"
                  label="API key"
                  saved={!!saved.zai_api_key}
                  configured={settings.zai_api_key_configured}
                  onClear={() => clearSecret('zai_api_key')}
                />
                <Input
                  id="zai_api_key"
                  type="password"
                  placeholder={
                    settings.zai_api_key_configured
                      ? 'Leave blank to keep the stored key'
                      : 'your Z.ai API key'
                  }
                  className="font-mono"
                  autoComplete="off"
                  error={errors.zai_api_key?.message}
                  {...registerWithSave('zai_api_key')}
                />
                <p className="mt-1.5 text-xs text-text-faint">
                  From the Z.ai console at z.ai/model-api
                </p>
              </div>
              <div>
                <LabelRow htmlFor="zai_model" label="Model" saved={!!saved.zai_model} />
                <Input
                  id="zai_model"
                  placeholder="glm-5.3"
                  className="font-mono"
                  error={errors.zai_model?.message}
                  {...registerWithSave('zai_model')}
                />
                <p className="mt-1.5 text-xs text-text-faint">
                  e.g. glm-5.3 (flagship), glm-5.3-flash (cheaper), glm-4.6
                </p>
              </div>
              <div>
                <LabelRow
                  htmlFor="zai_base_url"
                  label="Endpoint"
                  saved={!!saved.zai_base_url}
                />
                <Input
                  id="zai_base_url"
                  placeholder="https://api.z.ai/api/paas/v4/"
                  className="font-mono"
                  error={errors.zai_base_url?.message}
                  {...registerWithSave('zai_base_url')}
                />
                <p className="mt-1.5 text-xs text-text-faint">
                  Leave blank unless you use a regional or self-hosted endpoint.
                </p>
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
                <p className="mt-1.5 text-xs text-text-faint">
                  Your own Ollama server. Required — this provider runs on your hardware, not
                  StudyAIO's.
                </p>
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
        </div>
      </Card>

      <div className="flex items-center justify-between mt-4 pt-3 border-t border-border">
        <span className="text-xs text-text-faint">Changes save automatically</span>
      </div>
    </div>
  )
}

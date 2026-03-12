import { useEffect, useState } from 'react'
import { settingsApi } from '../api/endpoints'
import { BillingSection } from '../components/billing/BillingSection'
import { CalendarSyncSection } from '../components/calendar/CalendarSyncSection'
import { NotificationsSection } from '../components/notifications/NotificationsSection'
import { Card, ErrorBanner, LoadingSpinner, PageHeader } from '../components/ui'
import { useSettings, useUpdateSettings } from '../hooks/useApi'
import { useTheme, type Theme } from '../hooks/useTheme'
import { useTour } from '../hooks/useTour'
import type { Settings } from '../types'

const inputClass = 'w-full px-3 py-2 border border-border bg-surface text-text rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none'
const selectClass = `${inputClass} bg-surface`
const labelClass = 'block text-sm font-medium text-text mb-1'
const hintClass = 'mt-1 text-xs text-text-muted'

export function SettingsPage() {
  const { data: settings, isLoading, error } = useSettings()
  const updateMutation = useUpdateSettings()
  const { theme, setTheme } = useTheme()
  const { replay: replayTour } = useTour()
  const [form, setForm] = useState<Settings | null>(null)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [testingAi, setTestingAi] = useState(false)
  const [testResult, setTestResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    if (settings && !form) {
      setForm(settings) // eslint-disable-line react-hooks/set-state-in-effect
    }
  }, [settings, form])

  if (isLoading) return <LoadingSpinner />
  if (error) return <ErrorBanner message={error.message} />
  if (!form) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFeedback(null)
    try {
      await updateMutation.mutateAsync(form)
      setFeedback({ type: 'success', message: 'Settings saved successfully.' })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings'
      setFeedback({ type: 'error', message })
    }
  }

  const handleReset = () => {
    if (settings) {
      setForm(settings)
      setFeedback(null)
      setTestResult(null)
    }
  }

  const handleTestAi = async () => {
    setTestingAi(true)
    setTestResult(null)
    try {
      const result = await settingsApi.testAi()
      setTestResult({
        type: 'success',
        message: `${result.backend}: ${result.message}`,
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Connection test failed'
      setTestResult({ type: 'error', message })
    } finally {
      setTestingAi(false)
    }
  }

  const hasCliCredentials = !!(form.claude_cli_credentials && form.claude_cli_credentials.trim())

  const hasChanges = settings && JSON.stringify(form) !== JSON.stringify(settings)

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Appearance, AI providers, and pipeline configuration"
      />

      {feedback && (
        <div
          className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
            feedback.type === 'success'
              ? 'bg-green-50 dark:bg-green-950 text-green-800 dark:text-green-300 border border-green-200 dark:border-green-900'
              : 'bg-red-50 dark:bg-red-950 text-red-800 dark:text-red-300 border border-red-200 dark:border-red-900'
          }`}
        >
          {feedback.message}
        </div>
      )}

      {/* Plan & Billing */}
      <div className="mb-6">
        <BillingSection />
      </div>

      {/* Notifications */}
      <div className="mb-6">
        <NotificationsSection />
      </div>

      {/* Google Calendar */}
      <div className="mb-6">
        <CalendarSyncSection />
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Appearance */}
        <Card>
          <h2 className="text-lg font-semibold text-text mb-4">Appearance</h2>
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Theme</label>
              <div className="flex items-center gap-2">
                {(['light', 'dark', 'system'] as Theme[]).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTheme(t)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[44px] ${
                      theme === t
                        ? 'bg-primary text-white'
                        : 'bg-surface-alt text-text hover:bg-border'
                    }`}
                  >
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </button>
                ))}
              </div>
              <p className={hintClass}>Choose how StudyAIO looks. System follows your OS preference.</p>
            </div>

            <div>
              <label className={labelClass}>Onboarding Tour</label>
              <button
                type="button"
                onClick={replayTour}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface-alt transition-colors"
              >
                Replay Tour
              </button>
              <p className={hintClass}>Walk through the app's main features with a guided tour.</p>
            </div>
          </div>
        </Card>

        {/* AI Provider */}
        <Card>
          <h2 className="text-lg font-semibold text-text mb-4">AI Provider</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="agent_backend" className={labelClass}>Agent Backend</label>
              <select
                id="agent_backend"
                value={form.agent_backend}
                onChange={(e) => setForm({ ...form, agent_backend: e.target.value })}
                className={selectClass}
              >
                <option value="claude_code">Claude Code CLI</option>
                <option value="anthropic_api">Anthropic API (Direct)</option>
                <option value="openai">OpenAI</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
              <p className={hintClass}>Which AI provider to use for classification, summarization, and asset generation</p>
            </div>

            {/* Claude Code settings */}
            {form.agent_backend === 'claude_code' && (
              <>
                <div>
                  <label htmlFor="claude_code_path" className={labelClass}>Claude CLI Path</label>
                  <input
                    id="claude_code_path"
                    type="text"
                    value={form.claude_code_path}
                    onChange={(e) => setForm({ ...form, claude_code_path: e.target.value })}
                    className={inputClass}
                  />
                  <p className={hintClass}>Path to the Claude Code CLI binary</p>
                </div>
                <div>
                  <label htmlFor="claude_model" className={labelClass}>Claude Model</label>
                  <select
                    id="claude_model"
                    value={form.claude_model}
                    onChange={(e) => setForm({ ...form, claude_model: e.target.value })}
                    className={selectClass}
                  >
                    <option value="opus">Opus</option>
                    <option value="sonnet">Sonnet</option>
                    <option value="haiku">Haiku</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="claude_cli_credentials" className={labelClass}>
                    Claude CLI Credentials
                    {hasCliCredentials && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-300">
                        Configured
                      </span>
                    )}
                    {!hasCliCredentials && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-300">
                        Using system default
                      </span>
                    )}
                  </label>
                  <textarea
                    id="claude_cli_credentials"
                    value={form.claude_cli_credentials || ''}
                    onChange={(e) => setForm({ ...form, claude_cli_credentials: e.target.value })}
                    placeholder='Paste contents of ~/.claude/.credentials.json'
                    rows={4}
                    className={`${inputClass} font-mono text-xs`}
                  />
                  <p className={hintClass}>
                    To use your own Claude Max subscription: run <code className="px-1 py-0.5 bg-surface-alt rounded text-xs">claude login</code> on
                    your computer, then paste the contents of <code className="px-1 py-0.5 bg-surface-alt rounded text-xs">~/.claude/.credentials.json</code>.
                    Leave empty to use the system default credentials.
                  </p>
                </div>
              </>
            )}

            {/* Anthropic API settings */}
            {form.agent_backend === 'anthropic_api' && (
              <>
                <div>
                  <label htmlFor="anthropic_api_key" className={labelClass}>Anthropic API Key</label>
                  <input
                    id="anthropic_api_key"
                    type="password"
                    value={form.anthropic_api_key}
                    onChange={(e) => setForm({ ...form, anthropic_api_key: e.target.value })}
                    placeholder="sk-ant-..."
                    className={`${inputClass} font-mono`}
                  />
                  <p className={hintClass}>Your Anthropic API key for direct API access</p>
                </div>
                <div>
                  <label htmlFor="claude_model_api" className={labelClass}>Claude Model</label>
                  <select
                    id="claude_model_api"
                    value={form.claude_model}
                    onChange={(e) => setForm({ ...form, claude_model: e.target.value })}
                    className={selectClass}
                  >
                    <option value="opus">Opus</option>
                    <option value="sonnet">Sonnet</option>
                    <option value="haiku">Haiku</option>
                  </select>
                </div>
              </>
            )}

            {/* OpenAI settings */}
            {form.agent_backend === 'openai' && (
              <>
                <div>
                  <label htmlFor="openai_api_key" className={labelClass}>OpenAI API Key</label>
                  <input
                    id="openai_api_key"
                    type="password"
                    value={form.openai_api_key}
                    onChange={(e) => setForm({ ...form, openai_api_key: e.target.value })}
                    placeholder="sk-..."
                    className={`${inputClass} font-mono`}
                  />
                </div>
                <div>
                  <label htmlFor="openai_model" className={labelClass}>OpenAI Model</label>
                  <input
                    id="openai_model"
                    type="text"
                    value={form.openai_model}
                    onChange={(e) => setForm({ ...form, openai_model: e.target.value })}
                    placeholder="gpt-4o"
                    className={inputClass}
                  />
                  <p className={hintClass}>e.g. gpt-4o, gpt-4o-mini, o1</p>
                </div>
              </>
            )}

            {/* Ollama settings */}
            {form.agent_backend === 'ollama' && (
              <>
                <div>
                  <label htmlFor="ollama_base_url" className={labelClass}>Ollama Base URL</label>
                  <input
                    id="ollama_base_url"
                    type="text"
                    value={form.ollama_base_url}
                    onChange={(e) => setForm({ ...form, ollama_base_url: e.target.value })}
                    placeholder="http://ollama:11434"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label htmlFor="ollama_model" className={labelClass}>Ollama Model</label>
                  <input
                    id="ollama_model"
                    type="text"
                    value={form.ollama_model}
                    onChange={(e) => setForm({ ...form, ollama_model: e.target.value })}
                    placeholder="llama3.2"
                    className={inputClass}
                  />
                  <p className={hintClass}>Model name as shown in `ollama list`</p>
                </div>
              </>
            )}

            {/* Test Connection */}
            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={handleTestAi}
                disabled={testingAi || hasChanges === true}
                className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface-alt disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
              >
                {testingAi ? 'Testing...' : 'Test Connection'}
              </button>
              {hasChanges && (
                <span className="text-xs text-text-muted">Save settings first to test</span>
              )}
              {testResult && (
                <span className={`text-sm ${testResult.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {testResult.message}
                </span>
              )}
            </div>

            <div>
              <label htmlFor="classification_confidence_threshold" className={labelClass}>
                Classification Confidence Threshold
              </label>
              <input
                id="classification_confidence_threshold"
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={form.classification_confidence_threshold}
                onChange={(e) => setForm({ ...form, classification_confidence_threshold: parseFloat(e.target.value) || 0 })}
                className={inputClass}
              />
              <p className={hintClass}>Below this threshold, classifications go to review (0.0 - 1.0)</p>
            </div>

            <div>
              <label htmlFor="embedding_backend" className={labelClass}>Embedding Backend</label>
              <select
                id="embedding_backend"
                value={form.embedding_backend}
                onChange={(e) => setForm({ ...form, embedding_backend: e.target.value })}
                className={selectClass}
              >
                <option value="sentence_transformers">Sentence Transformers (Local)</option>
                <option value="openai">OpenAI Embeddings</option>
                <option value="ollama">Ollama Embeddings</option>
              </select>
              <p className={hintClass}>Backend used for generating text embeddings for similarity search</p>
            </div>
          </div>
        </Card>

        {/* Pipeline Tuning */}
        <Card>
          <h2 className="text-lg font-semibold text-text mb-4">Pipeline Tuning</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="flashcard_count_per_week" className={labelClass}>Flashcards per Week</label>
              <input
                id="flashcard_count_per_week"
                type="number"
                min={1}
                max={100}
                value={form.flashcard_count_per_week}
                onChange={(e) => setForm({ ...form, flashcard_count_per_week: parseInt(e.target.value) || 1 })}
                className={inputClass}
              />
              <p className={hintClass}>Number of flashcards generated per lecture (1-100)</p>
            </div>

            <div>
              <label htmlFor="quiz_question_count_per_week" className={labelClass}>Quiz Questions per Week</label>
              <input
                id="quiz_question_count_per_week"
                type="number"
                min={1}
                max={100}
                value={form.quiz_question_count_per_week}
                onChange={(e) => setForm({ ...form, quiz_question_count_per_week: parseInt(e.target.value) || 1 })}
                className={inputClass}
              />
              <p className={hintClass}>Number of quiz questions generated per lecture (1-100)</p>
            </div>

            <div>
              <label htmlFor="chunk_size_tokens" className={labelClass}>Chunk Size (tokens)</label>
              <input
                id="chunk_size_tokens"
                type="number"
                min={50}
                max={5000}
                value={form.chunk_size_tokens}
                onChange={(e) => setForm({ ...form, chunk_size_tokens: parseInt(e.target.value) || 50 })}
                className={inputClass}
              />
              <p className={hintClass}>Token window size for text chunking in the index stage (50-5000)</p>
            </div>

            <div>
              <label htmlFor="chunk_overlap_tokens" className={labelClass}>Chunk Overlap (tokens)</label>
              <input
                id="chunk_overlap_tokens"
                type="number"
                min={0}
                max={500}
                value={form.chunk_overlap_tokens}
                onChange={(e) => setForm({ ...form, chunk_overlap_tokens: parseInt(e.target.value) || 0 })}
                className={inputClass}
              />
              <p className={hintClass}>Overlap between consecutive chunks (0-500)</p>
            </div>
          </div>
        </Card>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={updateMutation.isPending || !hasChanges}
            className="px-4 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Settings'}
          </button>
          <button
            type="button"
            onClick={handleReset}
            disabled={!hasChanges}
            className="px-4 py-2 bg-surface text-text text-sm font-medium rounded-lg border border-border hover:bg-surface-alt disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  )
}

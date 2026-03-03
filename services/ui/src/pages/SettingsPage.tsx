import { useEffect, useState } from 'react'
import { Card, ErrorBanner, LoadingSpinner, PageHeader } from '../components/ui'
import { useSettings, useUpdateSettings } from '../hooks/useApi'
import type { Settings } from '../types'

export function SettingsPage() {
  const { data: settings, isLoading, error } = useSettings()
  const updateMutation = useUpdateSettings()
  const [form, setForm] = useState<Settings | null>(null)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  useEffect(() => {
    if (settings && !form) {
      setForm(settings)
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
    }
  }

  const hasChanges = settings && JSON.stringify(form) !== JSON.stringify(settings)

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Configure AI model, pipeline tuning, and system behavior"
      />

      {feedback && (
        <div
          className={`mb-4 px-4 py-3 rounded-lg text-sm font-medium ${
            feedback.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {feedback.message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* AI Configuration */}
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Configuration</h2>
          <div className="space-y-4">
            <div>
              <label htmlFor="agent_backend" className="block text-sm font-medium text-gray-700 mb-1">
                Agent Backend
              </label>
              <select
                id="agent_backend"
                value={form.agent_backend}
                onChange={(e) => setForm({ ...form, agent_backend: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none bg-white"
              >
                <option value="claude_code">Claude Code CLI</option>
                <option value="anthropic_api">Anthropic API (Direct)</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">How to connect to Claude: via CLI subprocess or direct API calls</p>
            </div>

            {form.agent_backend === 'claude_code' && (
              <div>
                <label htmlFor="claude_code_path" className="block text-sm font-medium text-gray-700 mb-1">
                  Claude CLI Path
                </label>
                <input
                  id="claude_code_path"
                  type="text"
                  value={form.claude_code_path}
                  onChange={(e) => setForm({ ...form, claude_code_path: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                />
                <p className="mt-1 text-xs text-gray-500">Path to the Claude Code CLI binary</p>
              </div>
            )}

            {form.agent_backend === 'anthropic_api' && (
              <div>
                <label htmlFor="anthropic_api_key" className="block text-sm font-medium text-gray-700 mb-1">
                  Anthropic API Key
                </label>
                <input
                  id="anthropic_api_key"
                  type="password"
                  value={form.anthropic_api_key}
                  onChange={(e) => setForm({ ...form, anthropic_api_key: e.target.value })}
                  placeholder="sk-ant-..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none font-mono"
                />
                <p className="mt-1 text-xs text-gray-500">Your Anthropic API key for direct API access</p>
              </div>
            )}

            <div>
              <label htmlFor="claude_model" className="block text-sm font-medium text-gray-700 mb-1">
                Claude Model
              </label>
              <select
                id="claude_model"
                value={form.claude_model}
                onChange={(e) => setForm({ ...form, claude_model: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none bg-white"
              >
                <option value="opus">Opus</option>
                <option value="sonnet">Sonnet</option>
                <option value="haiku">Haiku</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">AI model used for classification, summarization, and asset generation</p>
            </div>

            <div>
              <label htmlFor="classification_confidence_threshold" className="block text-sm font-medium text-gray-700 mb-1">
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
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">Below this threshold, classifications go to review (0.0 - 1.0)</p>
            </div>
          </div>
        </Card>

        {/* Pipeline Tuning */}
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Pipeline Tuning</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label htmlFor="flashcard_count_per_week" className="block text-sm font-medium text-gray-700 mb-1">
                Flashcards per Week
              </label>
              <input
                id="flashcard_count_per_week"
                type="number"
                min={1}
                max={100}
                value={form.flashcard_count_per_week}
                onChange={(e) => setForm({ ...form, flashcard_count_per_week: parseInt(e.target.value) || 1 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">Number of flashcards generated per lecture (1-100)</p>
            </div>

            <div>
              <label htmlFor="quiz_question_count_per_week" className="block text-sm font-medium text-gray-700 mb-1">
                Quiz Questions per Week
              </label>
              <input
                id="quiz_question_count_per_week"
                type="number"
                min={1}
                max={100}
                value={form.quiz_question_count_per_week}
                onChange={(e) => setForm({ ...form, quiz_question_count_per_week: parseInt(e.target.value) || 1 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">Number of quiz questions generated per lecture (1-100)</p>
            </div>

            <div>
              <label htmlFor="chunk_size_tokens" className="block text-sm font-medium text-gray-700 mb-1">
                Chunk Size (tokens)
              </label>
              <input
                id="chunk_size_tokens"
                type="number"
                min={50}
                max={5000}
                value={form.chunk_size_tokens}
                onChange={(e) => setForm({ ...form, chunk_size_tokens: parseInt(e.target.value) || 50 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">Token window size for text chunking in the index stage (50-5000)</p>
            </div>

            <div>
              <label htmlFor="chunk_overlap_tokens" className="block text-sm font-medium text-gray-700 mb-1">
                Chunk Overlap (tokens)
              </label>
              <input
                id="chunk_overlap_tokens"
                type="number"
                min={0}
                max={500}
                value={form.chunk_overlap_tokens}
                onChange={(e) => setForm({ ...form, chunk_overlap_tokens: parseInt(e.target.value) || 0 })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
              <p className="mt-1 text-xs text-gray-500">Overlap between consecutive chunks (0-500)</p>
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
            className="px-4 py-2 bg-white text-gray-700 text-sm font-medium rounded-lg border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors min-h-[44px]"
          >
            Reset
          </button>
        </div>
      </form>
    </div>
  )
}

interface SuggestionButtonsProps {
  suggestions: Record<string, unknown>
  onSelect: (resolution: Record<string, unknown>) => void
  isLoading: boolean
}

export function SuggestionButtons({ suggestions, onSelect, isLoading }: SuggestionButtonsProps) {
  const entries = Object.entries(suggestions)
  if (entries.length === 0) return null

  // If suggestions contain confidence, display as ranked options
  const hasConfidence = entries.some(([, v]) => typeof v === 'object' && v !== null && 'confidence' in (v as Record<string, unknown>))

  if (hasConfidence) {
    const options = entries
      .map(([key, val]) => {
        const obj = val as Record<string, unknown>
        return {
          key,
          value: obj.value ?? obj,
          confidence: typeof obj.confidence === 'number' ? obj.confidence : 0,
        }
      })
      .sort((a, b) => (b.confidence as number) - (a.confidence as number))

    return (
      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Suggestions</p>
        <div className="flex flex-wrap gap-2">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => onSelect({ [opt.key]: opt.value })}
              disabled={isLoading}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium rounded-lg border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 disabled:opacity-50 transition-colors"
            >
              <span>{String(opt.value)}</span>
              <span className="text-xs text-primary/60">{Math.round(opt.confidence * 100)}%</span>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // Simple key-value suggestions
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">Suggestions</p>
      <div className="flex flex-wrap gap-2">
        {entries.map(([key, value]) => (
          <button
            key={key}
            onClick={() => onSelect({ [key]: value })}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-primary/30 text-primary bg-primary/5 hover:bg-primary/10 disabled:opacity-50 transition-colors"
          >
            <span className="text-xs text-gray-400">{key}:</span>
            <span>{String(value)}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

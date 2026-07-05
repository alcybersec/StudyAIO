export type ReviewFilter = 'pending' | 'resolved' | 'dismissed'

const FILTERS: { id: ReviewFilter; label: string }[] = [
  { id: 'pending', label: 'Pending' },
  { id: 'resolved', label: 'Resolved' },
  { id: 'dismissed', label: 'Dismissed' },
]

interface ReviewFilterPillsProps {
  filter: ReviewFilter
  pendingCount: number
  onChange: (filter: ReviewFilter) => void
}

/** Status filter as compact pills; the pending pill carries a count. */
export function ReviewFilterPills({ filter, pendingCount, onChange }: ReviewFilterPillsProps) {
  return (
    <div className="flex items-center gap-1.5" role="tablist" aria-label="Filter review items">
      {FILTERS.map((f) => (
        <button
          key={f.id}
          role="tab"
          aria-selected={filter === f.id}
          onClick={() => onChange(f.id)}
          className={`text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
            filter === f.id
              ? 'bg-surface-2 border-border-strong text-text font-medium'
              : 'border-transparent text-text-muted hover:text-text hover:bg-surface-2'
          }`}
        >
          {f.label}
          {f.id === 'pending' && pendingCount > 0 && (
            <span className="font-mono text-[10px] ml-1.5 text-amber-fg">{pendingCount}</span>
          )}
        </button>
      ))}
    </div>
  )
}

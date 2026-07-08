import { useState } from 'react'
import { CheckCircle2, FileQuestion } from 'lucide-react'
import { Badge, Button, Card, EmptyState, ErrorState, FakeSelect, Input, Skeleton } from '../ui'
import { PageShell } from './shared'
import { useSim } from '../lib/sim'
import { reviewItems } from '../lib/mock'

function confidenceTone(c: number): 'red' | 'amber' | 'sage' {
  if (c < 40) return 'red'
  if (c < 60) return 'amber'
  return 'sage'
}

const FILTERS = [
  { label: 'Pending', count: 3, active: true },
  { label: 'Resolved', count: null, active: false },
  { label: 'Dismissed', count: null, active: false },
]

/* ------------------------------------------------------------ Row skeleton */

function RowSkeleton() {
  return (
    <div className="flex items-center gap-4 px-3 py-3">
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-48" />
        <Skeleton className="h-3 w-72" />
      </div>
      <Skeleton className="h-6 w-40" />
    </div>
  )
}

/* ------------------------------------------------------------------ Screen */

export function ReviewInbox() {
  const { sim } = useSim()
  // j/k selection is simulated: row 0 carries the focus ring.
  const [selected] = useState(0)
  // Row r2 shows the expanded inline-edit variant.
  const [editingId] = useState<string | null>('r2')

  return (
    <PageShell
      title="Review inbox"
      subtitle="Files the pipeline wasn't confident about — approve, correct, or dismiss."
      actions={
        <div className="flex items-center gap-1.5" role="tablist" aria-label="Filter review items">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              role="tab"
              aria-selected={f.active}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer ${
                f.active
                  ? 'bg-surface-2 border-border-strong text-text font-medium'
                  : 'border-transparent text-text-muted hover:text-text hover:bg-surface-2'
              }`}
            >
              {f.label}
              {f.count !== null && <span className="font-mono text-[10px] ml-1.5 text-amber-fg">{f.count}</span>}
            </button>
          ))}
        </div>
      }
      wide
    >
      {sim === 'loading' && (
        <Card dense className="p-0">
          <div className="divide-y divide-border" role="status" aria-label="Loading review items">
            <RowSkeleton />
            <RowSkeleton />
            <RowSkeleton />
          </div>
        </Card>
      )}

      {sim === 'error' && (
        <ErrorState
          title="Review inbox couldn't load"
          detail="GET /api/review-items?status=pending → 500 Internal Server Error"
          onRetry={() => {}}
        />
      )}

      {sim === 'empty' && (
        <Card className="border-sage/30 bg-sage-soft">
          <EmptyState
            icon={<CheckCircle2 size={28} strokeWidth={1.5} className="text-sage-fg" />}
            title="Inbox zero — nothing needs review"
            hint="New uploads land here only when classification confidence is low. You're all caught up."
            action={<Button variant="secondary" size="sm">Upload more lectures</Button>}
          />
        </Card>
      )}

      {(sim === 'default' || sim === 'offline') && (
        <>
          <Card dense className="p-0 overflow-hidden">
            <ul className="divide-y divide-border">
              {reviewItems.map((item, i) => {
                const tone = confidenceTone(item.guess.confidence)
                const isSelected = i === selected
                const isEditing = item.id === editingId
                return (
                  <li
                    key={item.id}
                    aria-current={isSelected ? 'true' : undefined}
                    className={`px-3 py-2.5 transition-colors ${
                      isSelected ? 'bg-surface-2 border-l-2 border-l-peri' : 'border-l-2 border-l-transparent hover:bg-surface-2/50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <FileQuestion size={14} className="text-text-faint shrink-0" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2.5 flex-wrap">
                          <span className="font-mono text-[13px]">{item.file}</span>
                          <span className="text-[13px] text-text-muted">
                            → <span className="text-text font-medium">{item.guess.course}</span> · wk {item.guess.week}
                          </span>
                          <Badge tone={tone}>{item.guess.confidence}% confident</Badge>
                        </div>
                        <p className="text-xs text-text-muted mt-0.5 truncate">{item.reason}</p>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button size="sm" kbd="A">Approve</Button>
                        <Button variant="secondary" size="sm" kbd="E">Edit</Button>
                        <Button variant="ghost" size="sm" kbd="D">Dismiss</Button>
                      </div>
                    </div>

                    {/* expanded inline edit */}
                    {isEditing && (
                      <div className="mt-2.5 ml-7 bg-surface-0 border border-border rounded-lg p-3 flex items-end gap-3 flex-wrap">
                        <FakeSelect label="Course" value={item.guess.course} className="w-44" />
                        <Input label="Week" id={`week-${item.id}`} defaultValue={String(item.guess.week)} className="w-20" inputMode="numeric" />
                        <div className="flex items-center gap-1.5 pb-0.5">
                          <Button size="sm" kbd="↵">Confirm</Button>
                          <Button variant="ghost" size="sm" kbd="esc">Cancel</Button>
                        </div>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </Card>

          <p className="text-[11px] font-mono text-text-faint mt-3 text-center">
            j/k navigate · a approve · e edit · d dismiss
          </p>
        </>
      )}
    </PageShell>
  )
}

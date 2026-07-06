import { useState } from 'react'
import { CalendarPlus } from 'lucide-react'
import { useCreateExamFromDeadline, useDeleteDeadline, useUpdateDeadline } from '../../hooks/useApi'
import { useCalendarStatus, useSyncCalendar } from '../../hooks/useCalendar'
import { Badge, EmptyState, ErrorState, Skeleton } from '../ui'
import type { Deadline } from '../../types'
import { daysUntil } from './dates'
import { DeadlineEditModal } from './DeadlineEditModal'

interface DeadlineTimelineProps {
  deadlines: Deadline[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

const TYPE_TONES: Record<string, { card: string; dot: string }> = {
  exam: { card: 'border-l-red bg-red-soft/40', dot: 'bg-red' },
  assignment: { card: 'border-l-peri bg-peri-soft/40', dot: 'bg-peri' },
  quiz: { card: 'border-l-amber bg-amber-soft/40', dot: 'bg-amber' },
  project: { card: 'border-l-peri bg-peri-soft/40', dot: 'bg-peri' },
  lab: { card: 'border-l-sage bg-sage-soft/40', dot: 'bg-sage' },
  presentation: { card: 'border-l-amber bg-amber-soft/40', dot: 'bg-amber' },
  other: { card: 'border-l-border-strong bg-surface-1', dot: 'bg-text-faint' },
}

function TimelineSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading deadlines">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="rounded-xl border border-border p-3 space-y-2">
          <Skeleton height={14} width="40%" />
          <Skeleton height={10} width="25%" />
        </div>
      ))}
    </div>
  )
}

export function DeadlineTimeline({ deadlines, isLoading, isError, onRetry }: DeadlineTimelineProps) {
  const [editingDeadline, setEditingDeadline] = useState<Deadline | null>(null)
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null)
  const updateDeadline = useUpdateDeadline()
  const deleteDeadline = useDeleteDeadline()
  const createExam = useCreateExamFromDeadline()
  const { data: calStatus } = useCalendarStatus()
  const syncCalendar = useSyncCalendar()
  const hasCalendar = (calStatus?.calendars?.length ?? 0) > 0

  if (isLoading && !deadlines) return <TimelineSkeleton />

  if (isError && !deadlines) {
    return <ErrorState title="Deadlines couldn't load" onRetry={onRetry} />
  }

  if (!deadlines || deadlines.length === 0) {
    return (
      <EmptyState
        title="No deadlines extracted yet"
        description="Upload a course outline in the Documents tab to get started."
      />
    )
  }

  return (
    <>
      <div className="space-y-3">
        {deadlines.map((d) => {
          const days = daysUntil(d.due_date)
          const isPast = days < 0
          const isUrgent = !isPast && days <= 3
          const isSoon = !isPast && !isUrgent && days <= 7
          const tone = TYPE_TONES[d.deadline_type] ?? TYPE_TONES.other

          return (
            <div
              key={d.id}
              className={`flex items-start gap-3 rounded-xl border border-border border-l-4 p-3 ${
                isPast ? 'border-l-border bg-surface-1 opacity-60' : tone.card
              }`}
            >
              <div className={`mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full ${isPast ? 'bg-text-faint' : tone.dot}`} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h4 className={`text-sm font-medium ${isPast ? 'text-text-muted line-through' : 'text-text'}`}>
                    {d.title}
                  </h4>
                  {d.is_confirmed && <Badge variant="success">confirmed</Badge>}
                  {isUrgent && <Badge variant="danger">urgent</Badge>}
                  {isSoon && <Badge variant="warning">soon</Badge>}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-text-muted">
                  <span className="font-mono text-[11px]">{d.due_date}</span>
                  <span className="capitalize">{d.deadline_type}</span>
                  {!isPast && <span className="font-mono text-[11px]">{days === 0 ? 'today' : `${days}d`}</span>}
                  {isPast && <span className="font-mono text-[11px]">past</span>}
                </div>
                {d.description && <p className="mt-1 text-xs text-text-muted">{d.description}</p>}
              </div>
              <div className="flex flex-shrink-0 items-center gap-1">
                {hasCalendar && (
                  <button
                    onClick={() => syncCalendar.mutate()}
                    disabled={syncCalendar.isPending}
                    className="rounded-md px-2 py-1 text-xs text-peri-fg hover:bg-peri-soft transition-colors disabled:opacity-50"
                    title="Sync to Google Calendar"
                    aria-label="Sync to Google Calendar"
                  >
                    <CalendarPlus size={14} aria-hidden />
                  </button>
                )}
                {!d.is_confirmed && (
                  <button
                    onClick={() => updateDeadline.mutate({ deadlineId: d.id, data: { is_confirmed: true } })}
                    className="rounded-md px-2 py-1 text-xs text-sage-fg hover:bg-sage-soft transition-colors"
                    title="Confirm deadline"
                  >
                    Confirm
                  </button>
                )}
                <button
                  onClick={() => setEditingDeadline(d)}
                  className="rounded-md px-2 py-1 text-xs text-peri-fg hover:bg-peri-soft transition-colors"
                >
                  Edit
                </button>
                {d.deadline_type === 'exam' && (
                  <button
                    onClick={() => createExam.mutate(d.id)}
                    disabled={createExam.isPending}
                    className="rounded-md px-2 py-1 text-xs text-peri-fg hover:bg-peri-soft transition-colors disabled:opacity-50"
                  >
                    Create Exam
                  </button>
                )}
                {confirmingDeleteId === d.id ? (
                  <span className="flex items-center gap-1">
                    <button
                      onClick={() => {
                        deleteDeadline.mutate(d.id)
                        setConfirmingDeleteId(null)
                      }}
                      className="rounded-md bg-red px-2 py-1 text-xs text-on-accent hover:opacity-90 transition-opacity"
                    >
                      Confirm
                    </button>
                    <button
                      onClick={() => setConfirmingDeleteId(null)}
                      className="rounded-md px-2 py-1 text-xs text-text-muted hover:bg-surface-2 transition-colors"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    onClick={() => setConfirmingDeleteId(d.id)}
                    className="rounded-md px-2 py-1 text-xs text-red-fg hover:bg-red-soft transition-colors"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {editingDeadline && <DeadlineEditModal deadline={editingDeadline} onClose={() => setEditingDeadline(null)} />}
    </>
  )
}

import { useState } from 'react'
import { useCreateExamFromDeadline, useDeleteDeadline, useUpdateDeadline } from '../../hooks/useApi'
import { useCalendarStatus, useSyncCalendar } from '../../hooks/useCalendar'
import type { Deadline } from '../../types'
import { DeadlineEditModal } from './DeadlineEditModal'

interface DeadlineTimelineProps {
  deadlines: Deadline[]
  isLoading: boolean
}

const TYPE_COLORS: Record<string, string> = {
  exam: 'border-red-400 bg-red-50',
  assignment: 'border-blue-400 bg-blue-50',
  quiz: 'border-yellow-400 bg-yellow-50',
  project: 'border-purple-400 bg-purple-50',
  lab: 'border-green-400 bg-green-50',
  presentation: 'border-orange-400 bg-orange-50',
  other: 'border-gray-400 bg-gray-50',
}

const TYPE_DOT: Record<string, string> = {
  exam: 'bg-red-500',
  assignment: 'bg-blue-500',
  quiz: 'bg-yellow-500',
  project: 'bg-purple-500',
  lab: 'bg-green-500',
  presentation: 'bg-orange-500',
  other: 'bg-gray-500',
}

function daysUntil(dateStr: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const due = new Date(dateStr)
  due.setHours(0, 0, 0, 0)
  return Math.ceil((due.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}

export function DeadlineTimeline({ deadlines, isLoading }: DeadlineTimelineProps) {
  const [editingDeadline, setEditingDeadline] = useState<Deadline | null>(null)
  const updateDeadline = useUpdateDeadline()
  const deleteDeadline = useDeleteDeadline()
  const createExam = useCreateExamFromDeadline()
  const { data: calStatus } = useCalendarStatus()
  const syncCalendar = useSyncCalendar()
  const hasCalendar = (calStatus?.calendars?.length ?? 0) > 0

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-gray-500">Loading deadlines...</div>
  }

  if (deadlines.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-gray-500">
        No deadlines extracted yet. Upload a course outline to get started.
      </div>
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

          return (
            <div
              key={d.id}
              className={`flex items-start gap-3 rounded-lg border-l-4 p-3 ${
                isPast ? 'border-gray-300 bg-gray-50 opacity-60' : TYPE_COLORS[d.deadline_type] ?? TYPE_COLORS.other
              }`}
            >
              <div className={`mt-1 h-2.5 w-2.5 flex-shrink-0 rounded-full ${TYPE_DOT[d.deadline_type] ?? TYPE_DOT.other}`} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h4 className={`text-sm font-medium ${isPast ? 'text-gray-500 line-through' : 'text-gray-900'}`}>
                    {d.title}
                  </h4>
                  {d.is_confirmed && (
                    <span className="inline-flex items-center rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700">
                      Confirmed
                    </span>
                  )}
                  {isUrgent && (
                    <span className="inline-flex items-center rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-700">
                      URGENT
                    </span>
                  )}
                  {isSoon && (
                    <span className="inline-flex items-center rounded bg-yellow-100 px-1.5 py-0.5 text-xs text-yellow-700">
                      Soon
                    </span>
                  )}
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                  <span>{d.due_date}</span>
                  <span className="capitalize">{d.deadline_type}</span>
                  {!isPast && <span>{days === 0 ? 'Today' : `${days}d`}</span>}
                  {isPast && <span>Past</span>}
                </div>
                {d.description && (
                  <p className="mt-1 text-xs text-gray-500">{d.description}</p>
                )}
              </div>
              <div className="flex flex-shrink-0 items-center gap-1">
                {hasCalendar && (
                  <button
                    onClick={() => syncCalendar.mutate()}
                    disabled={syncCalendar.isPending}
                    className="rounded px-2 py-1 text-xs text-primary hover:bg-primary/10"
                    title="Sync to Google Calendar"
                  >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </button>
                )}
                {!d.is_confirmed && (
                  <button
                    onClick={() =>
                      updateDeadline.mutate({ deadlineId: d.id, data: { is_confirmed: true } })
                    }
                    className="rounded px-2 py-1 text-xs text-green-600 hover:bg-green-100"
                    title="Confirm deadline"
                  >
                    Confirm
                  </button>
                )}
                <button
                  onClick={() => setEditingDeadline(d)}
                  className="rounded px-2 py-1 text-xs text-blue-600 hover:bg-blue-100"
                >
                  Edit
                </button>
                {d.deadline_type === 'exam' && (
                  <button
                    onClick={() => createExam.mutate(d.id)}
                    disabled={createExam.isPending}
                    className="rounded px-2 py-1 text-xs text-purple-600 hover:bg-purple-100"
                  >
                    Create Exam
                  </button>
                )}
                <button
                  onClick={() => {
                    if (confirm('Delete this deadline?')) {
                      deleteDeadline.mutate(d.id)
                    }
                  }}
                  className="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-100"
                >
                  Delete
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {editingDeadline && (
        <DeadlineEditModal
          deadline={editingDeadline}
          onClose={() => setEditingDeadline(null)}
        />
      )}
    </>
  )
}

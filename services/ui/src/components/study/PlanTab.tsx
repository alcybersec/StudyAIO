import { CalendarDays, Check } from 'lucide-react'
import { useStudyPlan } from '../../hooks/useApi'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { Button, Card, EmptyState, ErrorState, Skeleton } from '../ui'
import {
  formatPlanDayLabel,
  isPlanItemDone,
  isPlanToday,
  planCourses,
  planHasItems,
} from '../../lib/studyPlan'
import type { StudyPlanItem } from '../../types'

interface PlanTabProps {
  /** Jump to the flashcards tab to work today's queue. */
  onStartToday: () => void
  /** Jump to the exams tab to create an exam (empty-plan CTA). */
  onCreateExam: () => void
}

function chipLabel(item: StudyPlanItem): string {
  const what = `${item.target} ${item.kind}`
  if (item.done > 0 && !isPlanItemDone(item)) return `${item.done}/${what}`
  return what
}

function PlanSkeleton() {
  return (
    <Card padding={false} className="p-4" aria-busy="true">
      <div className="divide-y divide-border">
        {Array.from({ length: 7 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-2.5 px-1">
            <Skeleton width={32} height={14} />
            <Skeleton width={i % 2 ? 180 : 240} height={22} />
          </div>
        ))}
      </div>
    </Card>
  )
}

export function PlanTab({ onStartToday, onCreateExam }: PlanTabProps) {
  const { data, isLoading, error, refetch } = useStudyPlan()
  const online = useOnlineStatus()

  if (error) {
    return online ? (
      <ErrorState
        title="The weekly plan couldn't load"
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    ) : (
      <ErrorState
        title="You're offline"
        detail="The weekly plan needs a connection. It will load again once you're back online."
        onRetry={() => refetch()}
      />
    )
  }

  if (!data && !online) {
    return (
      <ErrorState
        title="You're offline"
        detail="The weekly plan needs a connection. It will load again once you're back online."
        onRetry={() => refetch()}
      />
    )
  }

  if (isLoading || !data) return <PlanSkeleton />

  if (!planHasItems(data.days)) {
    return (
      <EmptyState
        title="Nothing scheduled this week"
        description="Add an exam with a date and the planner builds a daily card schedule from your readiness."
        actionLabel="Create an exam"
        onAction={onCreateExam}
      />
    )
  }

  const courses = planCourses(data.days)

  return (
    <div className="max-w-3xl">
      <p className="text-[10px] font-mono font-medium uppercase tracking-[0.1em] text-text-faint mb-2">
        This week — built from {courses.join(' & ')}
      </p>
      <Card padding={false} className="p-4">
        <ul className="divide-y divide-border">
          {data.days.map((day) => {
            const today = isPlanToday(day.day)
            return (
              <li
                key={day.day}
                className={`flex items-center gap-4 py-2 px-1 ${
                  today ? 'bg-sage-soft -mx-3 px-4 rounded-lg' : ''
                }`}
              >
                <span
                  className={`font-mono text-[11px] w-8 shrink-0 ${
                    today ? 'text-sage-fg font-semibold' : 'text-text-faint'
                  }`}
                >
                  {formatPlanDayLabel(day.day)}
                </span>
                <div className="flex flex-wrap items-center gap-2 flex-1 min-h-[28px]">
                  {day.items.length === 0 && (
                    <span className="text-xs text-text-faint">rest day</span>
                  )}
                  {day.items.map((item, i) => {
                    const done = isPlanItemDone(item)
                    return (
                      <span
                        key={`${item.course_code}-${item.kind}-${i}`}
                        className={`inline-flex items-center gap-1.5 text-xs rounded-md px-2 py-1 bg-surface-2 ${
                          done ? 'text-text-faint line-through' : 'text-text'
                        }`}
                      >
                        {done && <Check size={11} className="text-sage-fg" aria-hidden />}
                        <span className="font-mono text-[10px] text-text-faint no-underline">
                          {item.course_code}
                        </span>
                        {chipLabel(item)}
                      </span>
                    )
                  })}
                </div>
                {today && (
                  <Button size="sm" onClick={onStartToday}>
                    Start
                  </Button>
                )}
              </li>
            )
          })}
        </ul>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-border text-[11px] text-text-faint">
          <span className="flex items-center gap-1.5">
            <CalendarDays size={11} aria-hidden /> targets scale with exam urgency
          </span>
          <button
            onClick={() => refetch()}
            className="hover:text-text-muted cursor-pointer underline underline-offset-2"
          >
            rebuild plan
          </button>
        </div>
      </Card>
    </div>
  )
}

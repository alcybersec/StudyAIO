import { memo } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardStudyStats } from '../../../hooks/useApi'
import { Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'

function StudySkeleton() {
  return (
    <div>
      <div className="flex justify-center my-3">
        <Skeleton height={32} width={64} />
      </div>
      <Skeleton height={8} width="100%" />
      <div className="grid grid-cols-3 gap-2 mt-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} height={44} />
        ))}
      </div>
    </div>
  )
}

export const StudyProgressWidget = memo(function StudyProgressWidget() {
  const { data, isLoading, isError, refetch } = useDashboardStudyStats()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || data.total === 0,
  })

  const masteryPct = data && data.total > 0 ? Math.round((data.mastered / data.total) * 100) : 0

  return (
    <WidgetShell
      title="Study progress"
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No flashcards yet"
      emptyHint="Cards are generated automatically when a lecture finishes processing."
      emptyActionLabel="Upload a lecture"
      emptyActionTo="/upload"
      skeleton={<StudySkeleton />}
    >
      {data && (
        <>
          <div className="flex items-center justify-between">
            <div>
              <span className="text-2xl font-bold text-text">{data.due_today}</span>
              <span className="text-xs text-text-muted ml-1.5">cards due today</span>
            </div>
            <Link
              to="/study"
              className="text-xs font-medium px-2.5 py-1.5 rounded-md bg-sage text-on-accent hover:bg-sage-hover transition-colors"
            >
              Study now
            </Link>
          </div>

          <div className="mt-3">
            <div className="flex items-center justify-between text-[11px] text-text-faint font-mono mb-1">
              <span>mastery</span>
              <span>{masteryPct}%</span>
            </div>
            <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
              <div className="h-full bg-sage rounded-full transition-all duration-500" style={{ width: `${masteryPct}%` }} />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center mt-3">
            {(
              [
                ['New', data.new],
                ['Learning', data.learning],
                ['Mastered', data.mastered],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="bg-surface-2 rounded-lg py-2">
                <p className="text-[13px] font-semibold text-text">{value}</p>
                <p className="text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint">{label}</p>
              </div>
            ))}
          </div>

          {data.per_course.length > 0 && (
            <ul className="border-t border-border mt-3 pt-2 space-y-1">
              {data.per_course.map((pc) => (
                <li key={pc.course_code} className="flex items-center justify-between text-xs">
                  <Link
                    to={`/study?course=${pc.course_code}`}
                    className="font-mono text-[11px] text-text-muted hover:text-text transition-colors"
                  >
                    {pc.course_code}
                  </Link>
                  <span className="text-text-faint">{pc.due_count} due</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </WidgetShell>
  )
})

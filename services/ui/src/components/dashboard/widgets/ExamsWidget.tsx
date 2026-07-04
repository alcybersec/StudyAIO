import { memo } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardExams } from '../../../hooks/useApi'
import { Badge, Skeleton } from '../../ui'
import { WidgetShell } from './WidgetShell'
import { selectWidgetState } from './widgetState'

function ExamsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
      {[0, 1].map((i) => (
        <div key={i} className="bg-surface-2 rounded-lg p-3 space-y-2.5">
          <Skeleton height={14} width="70%" />
          <Skeleton height={4} width="100%" />
          <Skeleton height={10} width="50%" />
        </div>
      ))}
    </div>
  )
}

export const ExamsWidget = memo(function ExamsWidget() {
  const { data, isLoading, isError, refetch } = useDashboardExams()
  const state = selectWidgetState({
    isLoading,
    isError,
    hasData: data !== undefined,
    isEmpty: !data || data.length === 0,
  })

  return (
    <WidgetShell
      title="Active exams"
      state={state}
      onRetry={() => refetch()}
      emptyTitle="No exams tracked"
      emptyHint="Create one from Study → Exams to get a readiness countdown."
      emptyActionLabel="Go to Exams"
      emptyActionTo="/study?tab=exams"
      skeleton={<ExamsSkeleton />}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
        {data?.map((exam) => (
          <Link
            key={exam.exam_id}
            to={`/study?tab=exams&exam=${exam.exam_id}`}
            className="bg-surface-2 hover:bg-surface-0 border border-transparent hover:border-border rounded-lg p-3 transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[13px] font-semibold text-text truncate">{exam.title}</span>
              <Badge variant={exam.days_remaining <= 7 ? 'danger' : 'default'}>{exam.days_remaining}d</Badge>
            </div>
            <div className="h-1 bg-surface-0 rounded-full mt-2.5 overflow-hidden">
              <div
                className={`h-full rounded-full ${exam.mastery_pct >= exam.target_mastery_pct ? 'bg-sage' : 'bg-amber'}`}
                style={{ width: `${Math.min(exam.mastery_pct, 100)}%` }}
              />
            </div>
            <div className="text-[11px] text-text-muted mt-1.5">
              <span className="font-mono text-[10px] text-text-faint">{exam.course_code}</span> · mastery{' '}
              <span className="font-medium text-text">{Math.round(exam.mastery_pct)}%</span> of{' '}
              {exam.target_mastery_pct}%
            </div>
          </Link>
        ))}
      </div>
    </WidgetShell>
  )
})

import { Link } from 'react-router-dom'
import type { DashboardExamSummary } from '../../types'

interface ExamCountdownProps {
  exams: DashboardExamSummary[]
}

export function ExamCountdown({ exams }: ExamCountdownProps) {
  if (exams.length === 0) return null

  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <h3 className="text-sm font-semibold text-text mb-3">Upcoming Exams</h3>
      <div className="space-y-3">
        {exams.map((exam) => {
          const urgencyColor =
            exam.days_remaining <= 3
              ? 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950'
              : exam.days_remaining <= 7
                ? 'text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950'
                : 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950'

          return (
            <Link
              key={exam.exam_id}
              to={`/study?tab=exams&exam=${exam.exam_id}`}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-surface-alt transition-colors group"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-text truncate group-hover:text-primary transition-colors">
                  {exam.title}
                </div>
                <div className="text-xs text-text-muted">{exam.course_code}</div>
              </div>
              <div className={`text-sm font-bold rounded-lg px-2.5 py-1 shrink-0 ml-3 ${urgencyColor}`}>
                {exam.days_remaining}d
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}

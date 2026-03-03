import { Link } from 'react-router-dom'
import type { DashboardExamSummary } from '../../types'

interface ExamCountdownProps {
  exams: DashboardExamSummary[]
}

export function ExamCountdown({ exams }: ExamCountdownProps) {
  if (exams.length === 0) return null

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">Upcoming Exams</h3>
      <div className="space-y-3">
        {exams.map((exam) => {
          const urgencyColor =
            exam.days_remaining <= 3
              ? 'text-red-600 bg-red-50'
              : exam.days_remaining <= 7
                ? 'text-amber-600 bg-amber-50'
                : 'text-blue-600 bg-blue-50'

          return (
            <Link
              key={exam.exam_id}
              to={`/exams/${exam.exam_id}`}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-gray-50 transition-colors group"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-900 truncate group-hover:text-primary transition-colors">
                  {exam.title}
                </div>
                <div className="text-xs text-gray-500">{exam.course_code}</div>
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

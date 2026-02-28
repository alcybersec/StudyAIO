import { Link } from 'react-router-dom'
import { StatusBadge } from '../ui'
import type { WeekSummaryRow } from '../../types'

interface WeekRowProps {
  courseCode: string
  week: WeekSummaryRow
}

export function WeekRow({ courseCode, week }: WeekRowProps) {
  const title = week.titles.length > 0 ? week.titles.join(', ') : 'Untitled'

  return (
    <Link
      to={`/courses/${courseCode}/weeks/${week.week}`}
      className="flex items-center gap-4 px-5 py-4 hover:bg-gray-50 transition-colors group"
    >
      <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-sm font-bold text-primary shrink-0">
        {week.week}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate group-hover:text-primary transition-colors">
          {title}
        </p>
        <p className="text-xs text-gray-500 mt-0.5">
          {week.artifact_count} file{week.artifact_count !== 1 ? 's' : ''}
          {week.flashcard_count > 0 && ` \u00B7 ${week.flashcard_count} flashcards`}
          {week.quiz_count > 0 && ` \u00B7 ${week.quiz_count} quizzes`}
        </p>
      </div>
      <StatusBadge status={week.summary_status} />
      <span className="text-gray-300 group-hover:text-gray-400 transition-colors">{'\u203A'}</span>
    </Link>
  )
}

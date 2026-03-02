import { Link } from 'react-router-dom'
import type { DashboardStudyStats } from '../../types'

interface StudyProgressProps {
  stats: DashboardStudyStats
}

export function StudyProgress({ stats }: StudyProgressProps) {
  const masteryPct = stats.total > 0
    ? Math.round((stats.mastered / stats.total) * 100)
    : 0

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-900">Study Progress</h2>
        <Link
          to="/study"
          className="px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-primary hover:bg-primary/90 transition-colors min-h-[32px] flex items-center"
        >
          Study Now
        </Link>
      </div>

      {/* Due count */}
      <div className="text-center mb-4">
        <p className="text-3xl font-bold text-gray-900">{stats.due_today}</p>
        <p className="text-sm text-gray-500">cards due today</p>
      </div>

      {/* Mastery bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>Mastery</span>
          <span>{masteryPct}%</span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 rounded-full transition-all duration-500"
            style={{ width: `${masteryPct}%` }}
          />
        </div>
      </div>

      {/* Breakdown */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs mb-4">
        <div className="bg-gray-50 rounded-lg py-2">
          <p className="font-semibold text-gray-900">{stats.new}</p>
          <p className="text-gray-500">New</p>
        </div>
        <div className="bg-gray-50 rounded-lg py-2">
          <p className="font-semibold text-gray-900">{stats.learning}</p>
          <p className="text-gray-500">Learning</p>
        </div>
        <div className="bg-gray-50 rounded-lg py-2">
          <p className="font-semibold text-gray-900">{stats.mastered}</p>
          <p className="text-gray-500">Mastered</p>
        </div>
      </div>

      {/* Per-course breakdown */}
      {stats.per_course.length > 0 && (
        <div className="border-t border-gray-100 pt-3 space-y-1.5">
          {stats.per_course.map((pc) => (
            <div key={pc.course_code} className="flex items-center justify-between text-xs">
              <Link
                to={`/study?course=${pc.course_code}`}
                className="font-medium text-gray-700 hover:text-primary transition-colors"
              >
                {pc.course_code}
              </Link>
              <span className="text-gray-500">
                {pc.due_count} due
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

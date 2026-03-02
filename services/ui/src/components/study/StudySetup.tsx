import { useCourses, useStudyStats } from '../../hooks/useApi'
import { LoadingSpinner } from '../ui'

interface StudySetupProps {
  courseCode: string
  week: string
  onCourseChange: (code: string) => void
  onWeekChange: (week: string) => void
  onStart: () => void
}

export function StudySetup({ courseCode, week, onCourseChange, onWeekChange, onStart }: StudySetupProps) {
  const { data: courses, isLoading: loadingCourses } = useCourses()
  const weekNum = week ? Number(week) : undefined
  const { data: stats, isLoading: loadingStats } = useStudyStats(
    courseCode || undefined,
    weekNum,
  )

  const dueCount = stats?.due_today ?? 0

  return (
    <div className="max-w-md mx-auto">
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <div>
          <label htmlFor="study-course" className="block text-sm font-medium text-gray-700 mb-1.5">
            Course
          </label>
          {loadingCourses ? (
            <LoadingSpinner label="" />
          ) : (
            <select
              id="study-course"
              value={courseCode}
              onChange={(e) => {
                onCourseChange(e.target.value)
                onWeekChange('')
              }}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            >
              <option value="">All courses</option>
              {courses?.map((c) => (
                <option key={c.id} value={c.code}>
                  {c.code}{c.name ? ` — ${c.name}` : ''}
                </option>
              ))}
            </select>
          )}
        </div>

        <div>
          <label htmlFor="study-week" className="block text-sm font-medium text-gray-700 mb-1.5">
            Week (optional)
          </label>
          <input
            id="study-week"
            type="number"
            min={1}
            max={52}
            placeholder="All weeks"
            value={week}
            onChange={(e) => onWeekChange(e.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>

        <div className="pt-2 text-center">
          {loadingStats ? (
            <LoadingSpinner label="Checking due cards..." />
          ) : (
            <>
              <p className="text-3xl font-bold text-gray-900 mb-1">{dueCount}</p>
              <p className="text-sm text-gray-500 mb-4">
                {dueCount === 1 ? 'card' : 'cards'} due for review
              </p>
            </>
          )}
        </div>

        <button
          onClick={onStart}
          disabled={dueCount === 0 || loadingStats}
          className="w-full py-3 px-4 rounded-lg text-sm font-semibold text-white bg-primary hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors min-h-[48px]"
        >
          Start Session
        </button>
      </div>
    </div>
  )
}

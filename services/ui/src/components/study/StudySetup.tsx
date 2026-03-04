import { Link } from 'react-router-dom'
import { useCourses, useStudyStats, useExams } from '../../hooks/useApi'
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
  const { data: activeExams } = useExams(courseCode || undefined, 'active')
  const weekNum = week ? Number(week) : undefined
  const { data: stats, isLoading: loadingStats } = useStudyStats(
    courseCode || undefined,
    weekNum,
  )

  const dueCount = stats?.due_today ?? 0

  return (
    <div className="max-w-md mx-auto">
      <div className="bg-surface rounded-xl border border-border p-6 space-y-5">
        <div>
          <label htmlFor="study-course" className="block text-sm font-medium text-text mb-1.5">
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
              className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
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
          <label htmlFor="study-week" className="block text-sm font-medium text-text mb-1.5">
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
            className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>

        <div className="pt-2 text-center">
          {loadingStats ? (
            <LoadingSpinner label="Checking due cards..." />
          ) : (
            <>
              <p className="text-3xl font-bold text-text mb-1">{dueCount}</p>
              <p className="text-sm text-text-muted mb-4">
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

        {activeExams && activeExams.length > 0 && (
          <div className="pt-2 border-t border-border">
            <p className="text-xs font-medium text-text-muted mb-2">Study for an exam:</p>
            <div className="space-y-1.5">
              {activeExams.map((exam) => (
                <Link
                  key={exam.id}
                  to={`/study?exam=${exam.id}`}
                  className="flex items-center justify-between w-full p-2.5 rounded-lg text-sm text-left bg-primary/5 hover:bg-primary/10 text-primary transition-colors min-h-[44px]"
                >
                  <span className="font-medium">{exam.title}</span>
                  <span className="text-xs opacity-70">{'\u{1F3AF}'}</span>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

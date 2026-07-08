import { Link } from 'react-router-dom'
import { Target } from 'lucide-react'
import { useCourses, useStudyStats, useExams } from '../../hooks/useApi'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { Button, Card, EmptyState, ErrorState, Skeleton } from '../ui'

interface StudySetupProps {
  courseCode: string
  week: string
  onCourseChange: (code: string) => void
  onWeekChange: (week: string) => void
  onStart: () => void
}

function SetupSkeleton() {
  return (
    <div className="max-w-md mx-auto" aria-busy="true">
      <Card className="space-y-5">
        <div className="space-y-2">
          <Skeleton width={60} height={12} />
          <Skeleton height={38} />
        </div>
        <div className="space-y-2">
          <Skeleton width={100} height={12} />
          <Skeleton height={38} />
        </div>
        <div className="flex flex-col items-center gap-2 py-2">
          <Skeleton width={56} height={32} />
          <Skeleton width={140} height={14} />
        </div>
        <Skeleton height={48} />
      </Card>
    </div>
  )
}

export function StudySetup({ courseCode, week, onCourseChange, onWeekChange, onStart }: StudySetupProps) {
  const { data: courses, isLoading: loadingCourses, error: coursesError, refetch } = useCourses()
  const { data: activeExams } = useExams(courseCode || undefined, 'active')
  const online = useOnlineStatus()
  const weekNum = week ? Number(week) : undefined
  const { data: stats, isLoading: loadingStats } = useStudyStats(
    courseCode || undefined,
    weekNum,
  )

  const dueCount = stats?.due_today ?? 0

  if (coursesError) {
    return (
      <div className="max-w-md mx-auto">
        <ErrorState
          title={online ? "Courses couldn't load" : "You're offline"}
          detail={coursesError instanceof Error ? coursesError.message : undefined}
          onRetry={() => refetch()}
        />
      </div>
    )
  }
  if (!courses && !online) {
    return (
      <div className="max-w-md mx-auto">
        <ErrorState
          title="You're offline"
          detail="The course list hasn't been cached. It will load once you're back online."
          onRetry={() => refetch()}
        />
      </div>
    )
  }
  if (loadingCourses || !courses) return <SetupSkeleton />

  if (courses.length === 0) {
    return (
      <EmptyState
        title="No courses yet"
        description="Upload lecture files and the pipeline will build flashcards you can study here."
        actionLabel="Upload lectures"
        actionTo="/upload"
      />
    )
  }

  return (
    <div className="max-w-md mx-auto">
      <Card className="space-y-5">
        <div>
          <label htmlFor="study-course" className="block text-xs font-medium text-text-muted mb-1.5">
            Course
          </label>
          <select
            id="study-course"
            value={courseCode}
            onChange={(e) => {
              onCourseChange(e.target.value)
              onWeekChange('')
            }}
            className="w-full rounded-lg border border-border bg-surface-1 text-text px-3 py-2.5 text-sm focus:outline-none focus:border-peri"
          >
            <option value="">All courses</option>
            {courses.map((c) => (
              <option key={c.id} value={c.code}>
                {c.code}{c.name ? ` — ${c.name}` : ''}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="study-week" className="block text-xs font-medium text-text-muted mb-1.5">
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
            className="w-full rounded-lg border border-border bg-surface-1 text-text placeholder:text-text-faint px-3 py-2.5 text-sm focus:outline-none focus:border-peri"
          />
        </div>

        <div className="pt-2 text-center">
          {loadingStats ? (
            <div className="flex flex-col items-center gap-2" aria-busy="true">
              <Skeleton width={56} height={32} />
              <Skeleton width={140} height={14} />
            </div>
          ) : (
            <>
              <p className="text-3xl font-bold font-mono text-text mb-1">{dueCount}</p>
              <p className="text-sm text-text-muted mb-4">
                {dueCount === 1 ? 'card' : 'cards'} due for review
              </p>
            </>
          )}
        </div>

        <Button
          size="lg"
          onClick={onStart}
          disabled={dueCount === 0 || loadingStats}
          className="w-full min-h-[48px]"
        >
          Start Session
        </Button>

        {activeExams && activeExams.length > 0 && (
          <div className="pt-2 border-t border-border">
            <p className="text-xs font-medium text-text-muted mb-2">Study for an exam:</p>
            <div className="space-y-1.5">
              {activeExams.map((exam) => (
                <Link
                  key={exam.id}
                  to={`/study?tab=flashcards&exam=${exam.id}`}
                  className="flex items-center justify-between w-full p-2.5 rounded-lg text-sm text-left bg-peri-soft hover:opacity-80 text-peri-fg transition-opacity min-h-[44px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
                >
                  <span className="font-medium">{exam.title}</span>
                  <Target size={14} className="opacity-70" aria-hidden />
                </Link>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}

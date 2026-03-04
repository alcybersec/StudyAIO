import { useAnalyticsOverview } from '../../hooks/useApi'
import { useExams } from '../../hooks/useApi'
import { Skeleton } from '../ui'
import { ExamReadiness } from './ExamReadiness'

function StatCard({ icon, value, label, loading }: {
  icon: React.ReactNode
  value: string | number
  label: string
  loading?: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        <div className="shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
        <div className="min-w-0">
          {loading ? (
            <Skeleton height={24} width={60} />
          ) : (
            <p className="text-xl font-bold text-text">{value}</p>
          )}
          <p className="text-xs text-text-muted">{label}</p>
        </div>
      </div>
    </div>
  )
}

const ClockIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const CardsIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 6.878V6a2.25 2.25 0 012.25-2.25h7.5A2.25 2.25 0 0118 6v.878m-12 0c.235-.083.487-.128.75-.128h10.5c.263 0 .515.045.75.128m-12 0A2.25 2.25 0 004.5 9v.878m13.5-3A2.25 2.25 0 0119.5 9v.878m0 0a2.246 2.246 0 00-.75-.128H5.25c-.263 0-.515.045-.75.128m15 0A2.25 2.25 0 0121 12v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6c0-1.243 1.007-2.25 2.25-2.25h13.5z" />
  </svg>
)

const MasteryIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.562.562 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.562.562 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
  </svg>
)

const CoursesIcon = (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
  </svg>
)

export function OverviewCards() {
  const { data, isLoading, error } = useAnalyticsOverview()
  const { data: exams } = useExams(undefined, 'active')

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-sm text-danger">Failed to load analytics overview.</p>
      </div>
    )
  }

  const hours = data ? data.total_study_hours.toFixed(1) : '0'
  const masteryPct = data ? `${Math.round(data.mastery_pct)}%` : '0%'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          icon={ClockIcon}
          value={hours}
          label="Study hours"
          loading={isLoading}
        />
        <StatCard
          icon={CardsIcon}
          value={data?.total_cards_reviewed ?? 0}
          label="Cards reviewed"
          loading={isLoading}
        />
        <StatCard
          icon={MasteryIcon}
          value={masteryPct}
          label="Mastery rate"
          loading={isLoading}
        />
        <StatCard
          icon={CoursesIcon}
          value={data?.active_courses ?? 0}
          label="Active courses"
          loading={isLoading}
        />
      </div>

      {/* Additional stats row */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-sm text-text-muted">Total sessions</p>
            <p className="text-lg font-semibold text-text mt-1">{data.total_sessions}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-sm text-text-muted">Total flashcards</p>
            <p className="text-lg font-semibold text-text mt-1">{data.total_flashcards}</p>
          </div>
          <div className="rounded-lg border border-border bg-surface p-4">
            <p className="text-sm text-text-muted">Mastered cards</p>
            <p className="text-lg font-semibold text-text mt-1">{data.mastered_flashcards}</p>
          </div>
        </div>
      )}

      {/* Exam readiness section */}
      {exams && exams.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-text mb-3">Exam Readiness</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {exams.map((exam) => (
              <ExamReadiness key={exam.id} examId={exam.id} />
            ))}
          </div>
        </div>
      )}

      {!isLoading && !data && (
        <div className="text-center py-8 text-text-muted text-sm">
          No study data yet. Start reviewing flashcards to see your analytics.
        </div>
      )}
    </div>
  )
}

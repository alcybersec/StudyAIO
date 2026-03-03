import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useExams } from '../hooks/useApi'
import { LoadingSpinner, ErrorBanner, PageHeader, EmptyState } from '../components/ui'
import { ExamCreateForm } from '../components/exam/ExamCreateForm'

export function ExamListPage() {
  const { data: exams, isLoading, error, refetch } = useExams(undefined, 'active')
  const [showCreate, setShowCreate] = useState(false)

  if (isLoading) return <LoadingSpinner label="Loading exams..." />
  if (error) return <ErrorBanner message="Failed to load exams." onRetry={refetch} />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <PageHeader title="Exams" subtitle={`${exams?.length ?? 0} active exam${(exams?.length ?? 0) !== 1 ? 's' : ''}`} />
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors"
        >
          + Create Exam
        </button>
      </div>

      {showCreate && (
        <div className="mb-6">
          <ExamCreateForm
            onClose={() => setShowCreate(false)}
            onCreated={() => refetch()}
          />
        </div>
      )}

      {!exams || exams.length === 0 ? (
        <EmptyState
          title="No active exams"
          description="Create an exam to start tracking your study progress and get adaptive study plans."
          actionLabel="Create Exam"
          onAction={() => setShowCreate(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {exams.map((exam) => {
            const examDate = new Date(exam.exam_date)
            const daysRemaining = Math.max(0, Math.ceil((examDate.getTime() - Date.now()) / 86400000))

            const urgencyColor =
              daysRemaining <= 3
                ? 'border-red-200 bg-red-50/50'
                : daysRemaining <= 7
                  ? 'border-amber-200 bg-amber-50/50'
                  : 'border-gray-200'

            return (
              <Link
                key={exam.id}
                to={`/exams/${exam.id}`}
                className={`block p-5 rounded-xl border ${urgencyColor} hover:shadow-md transition-all group`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-base font-semibold text-gray-900 group-hover:text-primary transition-colors">
                      {exam.title}
                    </h3>
                    <div className="text-sm text-gray-500 mt-0.5">
                      {examDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${
                    daysRemaining <= 3 ? 'text-red-600' : daysRemaining <= 7 ? 'text-amber-600' : 'text-gray-600'
                  }`}>
                    {daysRemaining}d
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {exam.weeks_scope.map((w) => (
                    <span key={w} className="px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs font-medium">
                      W{w}
                    </span>
                  ))}
                </div>

                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>Target: {exam.target_mastery_pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-gray-200 rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: '0%' }} />
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

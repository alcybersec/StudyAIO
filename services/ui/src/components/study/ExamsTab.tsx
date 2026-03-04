import { useState, useMemo } from 'react'
import { useExams } from '../../hooks/useApi'
import { LoadingSpinner, ErrorBanner, EmptyState } from '../ui'
import { ExamCreateForm } from '../exam/ExamCreateForm'
import { ExamDetailInline } from './ExamDetailInline'

interface ExamsTabProps {
  selectedExamId?: string | null
  onSelectExam: (id: string | null) => void
}

export function ExamsTab({ selectedExamId, onSelectExam }: ExamsTabProps) {
  const { data: exams, isLoading, error, refetch } = useExams(undefined, 'active')
  const [showCreate, setShowCreate] = useState(false)
  const now = useMemo(() => Date.now(), []) // eslint-disable-line react-hooks/purity

  // If an exam is selected, show its detail inline
  if (selectedExamId) {
    return (
      <ExamDetailInline
        examId={selectedExamId}
        onBack={() => onSelectExam(null)}
      />
    )
  }

  if (isLoading) return <LoadingSpinner label="Loading exams..." />
  if (error) return <ErrorBanner message="Failed to load exams." onRetry={refetch} />

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-text-muted">
          {exams?.length ?? 0} active exam{(exams?.length ?? 0) !== 1 ? 's' : ''}
        </p>
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
          description="Create an exam to start tracking your study progress."
          actionLabel="Create Exam"
          onAction={() => setShowCreate(true)}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {exams.map((exam) => {
            const examDate = new Date(exam.exam_date)
            const daysRemaining = Math.max(0, Math.ceil((examDate.getTime() - now) / 86400000))

            const urgencyColor =
              daysRemaining <= 3
                ? 'border-red-200 dark:border-red-900 bg-red-50/50 dark:bg-red-950/50'
                : daysRemaining <= 7
                  ? 'border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-950/50'
                  : 'border-border'

            return (
              <button
                key={exam.id}
                onClick={() => onSelectExam(exam.id)}
                className={`block w-full text-left p-5 rounded-xl border ${urgencyColor} hover:shadow-md transition-all group`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-base font-semibold text-text group-hover:text-primary transition-colors">
                      {exam.title}
                    </h3>
                    <div className="text-sm text-text-muted mt-0.5">
                      {examDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                    </div>
                  </div>
                  <div className={`text-lg font-bold ${
                    daysRemaining <= 3 ? 'text-red-600 dark:text-red-400' : daysRemaining <= 7 ? 'text-amber-600 dark:text-amber-400' : 'text-text-muted'
                  }`}>
                    {daysRemaining}d
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {exam.weeks_scope.map((w) => (
                    <span key={w} className="px-2 py-0.5 rounded-full bg-surface-alt text-text-muted text-xs font-medium">
                      W{w}
                    </span>
                  ))}
                </div>

                <div className="mt-3">
                  <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                    <span>Target: {exam.target_mastery_pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-border rounded-full overflow-hidden">
                    <div className="h-full bg-primary rounded-full" style={{ width: '0%' }} />
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

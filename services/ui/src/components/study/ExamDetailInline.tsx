import { useSearchParams } from 'react-router-dom'
import { useExamDetail, useExamSchedule, useExamWeakTopics, useExamHistory, useDeleteExam } from '../../hooks/useApi'
import { LoadingSpinner, ErrorBanner } from '../ui'

interface ExamDetailInlineProps {
  examId: string
  onBack: () => void
}

export function ExamDetailInline({ examId, onBack }: ExamDetailInlineProps) {
  const [, setSearchParams] = useSearchParams()
  const { data: progress, isLoading, error, refetch } = useExamDetail(examId)
  const { data: schedule } = useExamSchedule(examId)
  const { data: weakTopics } = useExamWeakTopics(examId)
  const { data: history } = useExamHistory(examId)
  const deleteExam = useDeleteExam()

  if (isLoading) return <LoadingSpinner label="Loading exam..." />
  if (error) return <ErrorBanner message="Failed to load exam." onRetry={refetch} />
  if (!progress) return null

  const urgencyColor =
    progress.days_remaining <= 3
      ? 'text-red-fg'
      : progress.days_remaining <= 7
        ? 'text-amber-fg'
        : 'text-peri-fg'

  const masteryPct = Math.round(progress.mastery_pct)
  const targetReached = masteryPct >= progress.target_mastery_pct

  async function handleArchive() {
    if (!confirm('Archive this exam?')) return
    await deleteExam.mutateAsync(examId)
    onBack()
  }

  function handleStudy() {
    setSearchParams({ tab: 'flashcards', exam: examId })
  }

  return (
    <div>
      <button
        onClick={onBack}
        className="text-sm text-text-muted hover:text-primary transition-colors mb-4"
      >
        {'\u2190'} Back to Exams
      </button>

      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-bold text-text">{progress.title}</h2>
          <div className="flex items-center gap-4 mt-1">
            <span className={`text-2xl font-bold ${urgencyColor}`}>
              {progress.days_remaining} days remaining
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              progress.status === 'active'
                ? 'bg-sage-soft text-sage-fg'
                : 'bg-surface-alt text-text-muted'
            }`}>
              {progress.status}
            </span>
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleStudy}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            Start Studying
          </button>
          <button
            onClick={handleArchive}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-surface-alt text-text hover:bg-border transition-colors"
          >
            Archive
          </button>
        </div>
      </div>

      {/* Progress Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="p-4 rounded-xl border border-border bg-surface">
          <div className="text-xs text-text-muted mb-1">Mastery</div>
          <div className="text-2xl font-bold text-text">{masteryPct}%</div>
          <div className="w-full h-1.5 bg-border rounded-full mt-2">
            <div
              className={`h-full rounded-full ${targetReached ? 'bg-sage' : 'bg-primary'}`}
              style={{ width: `${Math.min(100, masteryPct)}%` }}
            />
          </div>
          <div className="text-xs text-text-muted mt-1">Target: {progress.target_mastery_pct}%</div>
        </div>

        <div className="p-4 rounded-xl border border-border bg-surface">
          <div className="text-xs text-text-muted mb-1">Quiz Accuracy</div>
          <div className="text-2xl font-bold text-text">{Math.round(progress.quiz_accuracy)}%</div>
          <div className="text-xs text-text-muted mt-1">
            {progress.quiz_correct}/{progress.quiz_total} correct
          </div>
        </div>

        <div className="p-4 rounded-xl border border-border bg-surface">
          <div className="text-xs text-text-muted mb-1">Flashcards</div>
          <div className="text-2xl font-bold text-text">
            {progress.flashcard_mastered}/{progress.flashcard_total}
          </div>
          <div className="text-xs text-text-muted mt-1">mastered</div>
        </div>

        <div className="p-4 rounded-xl border border-border bg-surface">
          <div className="text-xs text-text-muted mb-1">Sessions</div>
          <div className="text-2xl font-bold text-text">{progress.session_count}</div>
          <div className="text-xs text-text-muted mt-1">study sessions</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Schedule */}
        {schedule && schedule.length > 0 && (
          <div className="bg-surface border border-border rounded-xl p-5">
            <h3 className="text-sm font-semibold text-text mb-4">Study Schedule</h3>
            <div className="space-y-2">
              {schedule.slice(0, 7).map((day) => {
                const priorityColor =
                  day.priority === 'critical' ? 'bg-red-soft text-red-fg'
                    : day.priority === 'high' ? 'bg-amber-soft text-amber-fg'
                      : day.priority === 'medium' ? 'bg-peri-soft text-peri-fg'
                        : 'bg-surface-alt text-text-muted'

                return (
                  <div key={day.date} className="flex items-center justify-between p-3 rounded-lg bg-surface-alt">
                    <div>
                      <div className="text-sm font-medium text-text">
                        {new Date(day.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                      </div>
                      <div className="text-xs text-text-muted">
                        {day.card_target} cards, {day.quiz_target} quiz | W{day.focus_weeks.join(', W')}
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${priorityColor}`}>
                      {day.priority}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Weak Topics */}
        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text mb-4">Weak Topics</h3>
          {!weakTopics || weakTopics.length === 0 ? (
            <div className="text-sm text-text-muted text-center py-6">
              No weak topics detected yet. Take some quizzes and review flashcards first.
            </div>
          ) : (
            <div className="space-y-2">
              {weakTopics.map((topic) => (
                <div key={topic.week} className="flex items-center justify-between p-3 rounded-lg bg-surface-alt">
                  <div>
                    <div className="text-sm font-medium text-text">Week {topic.week}</div>
                    <div className="text-xs text-text-muted">
                      {topic.reasons.map((r) => r.replace(/_/g, ' ')).join(', ')}
                    </div>
                  </div>
                  <div className="text-right">
                    {topic.quiz_accuracy !== null && (
                      <div className="text-xs text-text-muted">Quiz: {topic.quiz_accuracy}%</div>
                    )}
                    {topic.avg_ease !== null && (
                      <div className="text-xs text-text-muted">Ease: {topic.avg_ease}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Study History */}
        {history && history.length > 0 && (
          <div className="bg-surface border border-border rounded-xl p-5 lg:col-span-2">
            <h3 className="text-sm font-semibold text-text mb-4">Study History</h3>
            <div className="grid grid-cols-7 gap-1">
              {history.slice(0, 28).map((day) => {
                const intensity = day.cards_reviewed + day.quiz_answered
                const bg =
                  intensity === 0
                    ? 'bg-surface-alt'
                    : intensity < 10
                      ? 'bg-sage/30'
                      : intensity < 25
                        ? 'bg-sage/60'
                        : 'bg-sage'

                return (
                  <div
                    key={day.date}
                    className={`w-full aspect-square rounded-sm ${bg}`}
                    title={`${day.date}: ${day.cards_reviewed} cards, ${day.quiz_answered} quiz`}
                  />
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

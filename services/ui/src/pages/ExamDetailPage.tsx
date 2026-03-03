import { useParams, Link, useNavigate } from 'react-router-dom'
import { useExamDetail, useExamSchedule, useExamWeakTopics, useExamHistory, useDeleteExam } from '../hooks/useApi'
import { LoadingSpinner, ErrorBanner, PageHeader } from '../components/ui'

export function ExamDetailPage() {
  const { examId } = useParams<{ examId: string }>()
  const navigate = useNavigate()
  const { data: progress, isLoading, error, refetch } = useExamDetail(examId!)
  const { data: schedule } = useExamSchedule(examId!)
  const { data: weakTopics } = useExamWeakTopics(examId!)
  const { data: history } = useExamHistory(examId!)
  const deleteExam = useDeleteExam()

  if (isLoading) return <LoadingSpinner label="Loading exam..." />
  if (error) return <ErrorBanner message="Failed to load exam." onRetry={refetch} />
  if (!progress) return null

  const urgencyColor =
    progress.days_remaining <= 3
      ? 'text-red-600'
      : progress.days_remaining <= 7
        ? 'text-amber-600'
        : 'text-blue-600'

  const masteryPct = Math.round(progress.mastery_pct)
  const targetReached = masteryPct >= progress.target_mastery_pct

  async function handleArchive() {
    if (!confirm('Archive this exam?')) return
    await deleteExam.mutateAsync(examId!)
    navigate('/exams')
  }

  return (
    <div>
      <div className="mb-2">
        <Link to="/exams" className="text-sm text-gray-500 hover:text-primary transition-colors">
          {'\u2190'} Back to Exams
        </Link>
      </div>

      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4 mb-8">
        <div>
          <PageHeader title={progress.title} />
          <div className="flex items-center gap-4 mt-1">
            <span className={`text-2xl font-bold ${urgencyColor}`}>
              {progress.days_remaining} days remaining
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              progress.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
            }`}>
              {progress.status}
            </span>
          </div>
        </div>

        <div className="flex gap-2">
          <Link
            to={`/study?exam=${examId}`}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors"
          >
            Start Studying
          </Link>
          <button
            onClick={handleArchive}
            className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
          >
            Archive
          </button>
        </div>
      </div>

      {/* Progress Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="p-4 rounded-xl border border-gray-200 bg-white">
          <div className="text-xs text-gray-500 mb-1">Mastery</div>
          <div className="text-2xl font-bold text-gray-900">{masteryPct}%</div>
          <div className="w-full h-1.5 bg-gray-200 rounded-full mt-2">
            <div
              className={`h-full rounded-full ${targetReached ? 'bg-green-500' : 'bg-primary'}`}
              style={{ width: `${Math.min(100, masteryPct)}%` }}
            />
          </div>
          <div className="text-xs text-gray-400 mt-1">Target: {progress.target_mastery_pct}%</div>
        </div>

        <div className="p-4 rounded-xl border border-gray-200 bg-white">
          <div className="text-xs text-gray-500 mb-1">Quiz Accuracy</div>
          <div className="text-2xl font-bold text-gray-900">{Math.round(progress.quiz_accuracy)}%</div>
          <div className="text-xs text-gray-400 mt-1">
            {progress.quiz_correct}/{progress.quiz_total} correct
          </div>
        </div>

        <div className="p-4 rounded-xl border border-gray-200 bg-white">
          <div className="text-xs text-gray-500 mb-1">Flashcards</div>
          <div className="text-2xl font-bold text-gray-900">
            {progress.flashcard_mastered}/{progress.flashcard_total}
          </div>
          <div className="text-xs text-gray-400 mt-1">mastered</div>
        </div>

        <div className="p-4 rounded-xl border border-gray-200 bg-white">
          <div className="text-xs text-gray-500 mb-1">Sessions</div>
          <div className="text-2xl font-bold text-gray-900">{progress.session_count}</div>
          <div className="text-xs text-gray-400 mt-1">study sessions</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Plan */}
        {schedule && schedule.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Study Schedule</h3>
            <div className="space-y-2">
              {schedule.slice(0, 7).map((day) => {
                const priorityColor =
                  day.priority === 'critical' ? 'bg-red-100 text-red-700'
                    : day.priority === 'high' ? 'bg-amber-100 text-amber-700'
                      : day.priority === 'medium' ? 'bg-blue-100 text-blue-700'
                        : 'bg-gray-100 text-gray-600'

                return (
                  <div key={day.date} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {new Date(day.date + 'T00:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
                      </div>
                      <div className="text-xs text-gray-500">
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
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-gray-900 mb-4">Weak Topics</h3>
          {!weakTopics || weakTopics.length === 0 ? (
            <div className="text-sm text-gray-500 text-center py-6">
              No weak topics detected yet. Take some quizzes and review flashcards first.
            </div>
          ) : (
            <div className="space-y-2">
              {weakTopics.map((topic) => (
                <div key={topic.week} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                  <div>
                    <div className="text-sm font-medium text-gray-900">Week {topic.week}</div>
                    <div className="text-xs text-gray-500">
                      {topic.reasons.map((r) => r.replace(/_/g, ' ')).join(', ')}
                    </div>
                  </div>
                  <div className="text-right">
                    {topic.quiz_accuracy !== null && (
                      <div className="text-xs text-gray-600">Quiz: {topic.quiz_accuracy}%</div>
                    )}
                    {topic.avg_ease !== null && (
                      <div className="text-xs text-gray-600">Ease: {topic.avg_ease}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Study History */}
        {history && history.length > 0 && (
          <div className="bg-white border border-gray-200 rounded-xl p-5 lg:col-span-2">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Study History</h3>
            <div className="grid grid-cols-7 gap-1">
              {history.slice(0, 28).map((day) => {
                const intensity = day.cards_reviewed + day.quiz_answered
                const bg =
                  intensity === 0
                    ? 'bg-gray-100'
                    : intensity < 10
                      ? 'bg-green-200'
                      : intensity < 25
                        ? 'bg-green-400'
                        : 'bg-green-600'

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

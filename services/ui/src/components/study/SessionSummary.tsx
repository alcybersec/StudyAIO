import { Link } from 'react-router-dom'
import { useStreak } from '../../hooks/useApi'

interface SessionSummaryProps {
  totalReviewed: number
  ratings: Record<number, number>
  onRestart: () => void
  examId?: string
}

const ratingLabels: Record<number, { label: string; color: string }> = {
  1: { label: 'Again', color: 'text-red-600' },
  2: { label: 'Hard', color: 'text-orange-600' },
  3: { label: 'Good', color: 'text-green-600' },
  5: { label: 'Easy', color: 'text-blue-600' },
}

export function SessionSummary({ totalReviewed, ratings, onRestart, examId }: SessionSummaryProps) {
  const { data: streak } = useStreak()

  return (
    <div className="max-w-md mx-auto text-center">
      <div className="bg-white rounded-xl border border-gray-200 p-8 space-y-6">
        <div className="text-4xl mb-2">&#10003;</div>
        <h2 className="text-xl font-bold text-gray-900">Session Complete</h2>
        <p className="text-gray-500">
          You reviewed <span className="font-semibold text-gray-900">{totalReviewed}</span>{' '}
          {totalReviewed === 1 ? 'card' : 'cards'}
        </p>

        {streak && streak.current_streak > 0 && (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-600">
            <span className="text-lg">{'\u{1F525}'}</span>
            <span>{streak.current_streak} day streak</span>
          </div>
        )}

        <div className="space-y-2">
          {Object.entries(ratingLabels).map(([q, { label, color }]) => {
            const count = ratings[Number(q)] || 0
            if (count === 0) return null
            return (
              <div key={q} className="flex items-center justify-between px-4">
                <span className={`text-sm font-medium ${color}`}>{label}</span>
                <span className="text-sm text-gray-600">{count}</span>
              </div>
            )
          })}
        </div>

        <div className="flex flex-col gap-3 pt-2">
          <button
            onClick={onRestart}
            className="w-full py-3 px-4 rounded-lg text-sm font-semibold text-white bg-primary hover:bg-primary/90 transition-colors min-h-[48px]"
          >
            Study More
          </button>
          {examId ? (
            <Link
              to={`/exams/${examId}`}
              className="w-full py-3 px-4 rounded-lg text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors text-center min-h-[48px] flex items-center justify-center"
            >
              Back to Exam
            </Link>
          ) : (
            <Link
              to="/"
              className="w-full py-3 px-4 rounded-lg text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors text-center min-h-[48px] flex items-center justify-center"
            >
              Back to Dashboard
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}

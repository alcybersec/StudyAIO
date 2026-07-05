import { Link } from 'react-router-dom'
import { Check, Flame } from 'lucide-react'
import { useStreak } from '../../hooks/useApi'
import { Button, Card } from '../ui'

interface SessionSummaryProps {
  totalReviewed: number
  ratings: Record<number, number>
  onRestart: () => void
  examId?: string
}

const ratingLabels: Record<number, { label: string; tone: string }> = {
  1: { label: 'Again', tone: 'text-red-fg' },
  2: { label: 'Hard', tone: 'text-amber-fg' },
  3: { label: 'Good', tone: 'text-sage-fg' },
  5: { label: 'Easy', tone: 'text-peri-fg' },
}

export function SessionSummary({ totalReviewed, ratings, onRestart, examId }: SessionSummaryProps) {
  const { data: streak } = useStreak()

  return (
    <div className="max-w-md mx-auto text-center">
      <Card padding={false} className="p-8 space-y-6">
        <div className="mx-auto w-12 h-12 rounded-full bg-sage-soft flex items-center justify-center">
          <Check size={24} className="text-sage-fg" aria-hidden />
        </div>
        <h2 className="text-xl font-bold text-text">Session Complete</h2>
        <p className="text-text-muted">
          You reviewed <span className="font-semibold text-text">{totalReviewed}</span>{' '}
          {totalReviewed === 1 ? 'card' : 'cards'}
        </p>

        {streak && streak.current_streak > 0 && (
          <div className="flex items-center justify-center gap-2 text-sm text-text-muted">
            <Flame size={16} className="text-amber-fg" aria-hidden />
            <span>{streak.current_streak} day streak</span>
          </div>
        )}

        <div className="space-y-2">
          {Object.entries(ratingLabels).map(([q, { label, tone }]) => {
            const count = ratings[Number(q)] || 0
            if (count === 0) return null
            return (
              <div key={q} className="flex items-center justify-between px-4">
                <span className={`text-sm font-medium ${tone}`}>{label}</span>
                <span className="text-sm font-mono text-text-muted">{count}</span>
              </div>
            )
          })}
        </div>

        <div className="flex flex-col gap-3 pt-2">
          <Button size="lg" onClick={onRestart} className="w-full min-h-[48px]">
            Study More
          </Button>
          <Link
            to={examId ? `/study?tab=exams&exam=${examId}` : '/'}
            className="w-full py-3 px-4 rounded-lg text-sm font-medium text-text bg-surface-2 border border-border hover:border-border-strong transition-colors text-center min-h-[48px] flex items-center justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
          >
            {examId ? 'Back to Exam' : 'Back to Dashboard'}
          </Link>
        </div>
      </Card>
    </div>
  )
}

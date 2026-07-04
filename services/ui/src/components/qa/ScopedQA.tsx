import { useNavigate } from 'react-router-dom'
import { MessageSquare } from 'lucide-react'
import { Button } from '../ui/Button'

interface ScopedQAProps {
  courseCode: string
  week: number
  /** Kept for call-site compatibility; citations now open inside Ask. */
  onCitationClick?: (artifactId: string, page: number) => void
}

/**
 * Week-scoped Q&A moved into the merged Ask surface — this panel hands
 * off to /ask with the course/week scope chips prefilled.
 */
export function ScopedQA({ courseCode, week }: ScopedQAProps) {
  const navigate = useNavigate()

  return (
    <div className="flex flex-col items-center justify-center text-center py-10 px-4">
      <MessageSquare size={40} strokeWidth={1.2} className="text-text-faint mb-4" aria-hidden />
      <h3 className="text-base font-semibold text-text mb-1">Ask about this week</h3>
      <p className="text-sm text-text-muted mb-5 max-w-sm">
        Questions now live in Ask — answers cite their sources, and this one starts scoped to{' '}
        <span className="font-medium text-text">
          {courseCode} · Week {week}
        </span>
        .
      </p>
      <Button onClick={() => navigate(`/ask?course=${encodeURIComponent(courseCode)}&week=${week}`)}>
        Ask about {courseCode} Week {week}
      </Button>
    </div>
  )
}

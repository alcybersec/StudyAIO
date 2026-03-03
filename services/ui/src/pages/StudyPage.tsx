import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useStudyDue, useRecordReview, useExamDetail } from '../hooks/useApi'
import { examsApi } from '../api/endpoints'
import { PageHeader, LoadingSpinner, EmptyState } from '../components/ui'
import { StudySetup } from '../components/study/StudySetup'
import { StudyCard } from '../components/study/StudyCard'
import { RatingButtons } from '../components/study/RatingButtons'
import { SessionSummary } from '../components/study/SessionSummary'

type Phase = 'setup' | 'studying' | 'done'

export function StudyPage() {
  const [searchParams] = useSearchParams()
  const [courseCode, setCourseCode] = useState(searchParams.get('course') ?? '')
  const [week, setWeek] = useState(searchParams.get('week') ?? '')
  const [examId] = useState(searchParams.get('exam') ?? '')
  const [phase, setPhase] = useState<Phase>(examId ? 'studying' : 'setup')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [sessionRatings, setSessionRatings] = useState<Record<number, number>>({})
  const [totalReviewed, setTotalReviewed] = useState(0)
  const startTime = useRef(Date.now())

  // Pre-fetch exam detail when in exam mode (used by sub-components)
  useExamDetail(examId || '')

  const weekNum = week ? Number(week) : undefined
  const { data: dueCards, isLoading, refetch } = useStudyDue(
    courseCode || undefined,
    weekNum,
    50,
  )
  const reviewMutation = useRecordReview()

  const cards = dueCards ?? []
  const currentCard = cards[currentIndex]

  const handleStart = useCallback(() => {
    if (cards.length > 0) {
      setCurrentIndex(0)
      setFlipped(false)
      setSessionRatings({})
      setTotalReviewed(0)
      setPhase('studying')
    }
  }, [cards.length])

  const handleFlip = useCallback(() => {
    setFlipped((f) => !f)
  }, [])

  const handleRate = useCallback((quality: number) => {
    if (!currentCard || reviewMutation.isPending) return

    reviewMutation.mutate(
      { flashcard_id: currentCard.id, quality },
      {
        onSuccess: () => {
          setSessionRatings((prev) => ({
            ...prev,
            [quality]: (prev[quality] || 0) + 1,
          }))
          setTotalReviewed((n) => n + 1)

          if (currentIndex < cards.length - 1) {
            setCurrentIndex((i) => i + 1)
            setFlipped(false)
          } else {
            // Record session to backend if in exam mode
            if (examId) {
              const duration = Math.round((Date.now() - startTime.current) / 1000)
              examsApi.recordSession(examId, {
                cards_reviewed: totalReviewed + 1,
                quiz_questions_answered: 0,
                quiz_correct: 0,
                duration_seconds: duration,
              }).catch(() => {})
            }
            setPhase('done')
          }
        },
      },
    )
  }, [currentCard, currentIndex, cards.length, reviewMutation])

  const handleRestart = useCallback(() => {
    refetch()
    setPhase('setup')
    setCurrentIndex(0)
    setFlipped(false)
  }, [refetch])

  // Keyboard shortcuts
  useEffect(() => {
    if (phase !== 'studying') return

    function handleKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return

      if ((e.key === ' ' || e.key === 'Enter') && !flipped) {
        e.preventDefault()
        setFlipped(true)
      } else if (flipped) {
        const keyMap: Record<string, number> = { '1': 1, '2': 2, '3': 3, '4': 5 }
        const quality = keyMap[e.key]
        if (quality !== undefined) {
          e.preventDefault()
          handleRate(quality)
        }
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [phase, flipped, handleRate])

  if (phase === 'done') {
    return (
      <div>
        <PageHeader title="Study Session" />
        <SessionSummary
          totalReviewed={totalReviewed}
          ratings={sessionRatings}
          onRestart={handleRestart}
          examId={examId || undefined}
        />
      </div>
    )
  }

  if (phase === 'setup') {
    return (
      <div>
        <PageHeader title="Study" subtitle="Spaced repetition flashcard review" />
        <StudySetup
          courseCode={courseCode}
          week={week}
          onCourseChange={setCourseCode}
          onWeekChange={setWeek}
          onStart={handleStart}
        />
      </div>
    )
  }

  // Studying phase
  if (isLoading) return <LoadingSpinner label="Loading cards..." />

  if (!currentCard) {
    return (
      <div>
        <PageHeader title="Study Session" />
        <EmptyState
          icon="&#10003;"
          title="All caught up!"
          description="No more cards due right now. Check back later."
        />
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Study Session"
        subtitle={`Card ${currentIndex + 1} of ${cards.length}`}
      />

      <div className="space-y-6">
        <StudyCard card={currentCard} onFlip={handleFlip} flipped={flipped} />

        {flipped && (
          <RatingButtons onRate={handleRate} disabled={reviewMutation.isPending} />
        )}
      </div>
    </div>
  )
}

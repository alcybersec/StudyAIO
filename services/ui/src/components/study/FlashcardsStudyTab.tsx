import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useStudyDue, useRecordReview, useExamDetail } from '../../hooks/useApi'
import { examsApi } from '../../api/endpoints'
import { writeQueue } from '../../lib/writeQueue'
import { LoadingSpinner, EmptyState } from '../ui'
import { StudySetup } from './StudySetup'
import { StudyCard } from './StudyCard'
import { RatingButtons } from './RatingButtons'
import { SessionSummary } from './SessionSummary'

type Phase = 'setup' | 'studying' | 'done'

export function FlashcardsStudyTab() {
  const [searchParams] = useSearchParams()
  const [courseCode, setCourseCode] = useState(searchParams.get('course') ?? '')
  const [week, setWeek] = useState(searchParams.get('week') ?? '')
  const [examId] = useState(searchParams.get('exam') ?? '')
  const [phase, setPhase] = useState<Phase>(examId ? 'studying' : 'setup')
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [sessionRatings, setSessionRatings] = useState<Record<number, number>>({})
  const [totalReviewed, setTotalReviewed] = useState(0)
  const [startTimeVal] = useState(() => Date.now())
  const startTime = useRef(startTimeVal)

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
            if (examId) {
              const duration = Math.round((Date.now() - startTime.current) / 1000)
              const session = {
                cards_reviewed: totalReviewed + 1,
                quiz_questions_answered: 0,
                quiz_correct: 0,
                duration_seconds: duration,
              }
              examsApi.recordSession(examId, session).catch(() => {
                void writeQueue.enqueue({
                  url: `/api/exams/${examId}/sessions`,
                  method: 'POST',
                  body: JSON.stringify(session),
                })
              })
            }
            setPhase('done')
          }
        },
      },
    )
  }, [currentCard, currentIndex, cards.length, reviewMutation, examId, totalReviewed])

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
      <SessionSummary
        totalReviewed={totalReviewed}
        ratings={sessionRatings}
        onRestart={handleRestart}
        examId={examId || undefined}
      />
    )
  }

  if (phase === 'setup') {
    return (
      <StudySetup
        courseCode={courseCode}
        week={week}
        onCourseChange={setCourseCode}
        onWeekChange={setWeek}
        onStart={handleStart}
      />
    )
  }

  if (isLoading) return <LoadingSpinner label="Loading cards..." />

  if (!currentCard) {
    return (
      <EmptyState
        icon="&#10003;"
        title="All caught up!"
        description="No more cards due right now. Check back later."
      />
    )
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-text-muted text-center">
        Card {currentIndex + 1} of {cards.length}
      </p>
      <StudyCard card={currentCard} onFlip={handleFlip} flipped={flipped} />
      {flipped && (
        <RatingButtons onRate={handleRate} disabled={reviewMutation.isPending} />
      )}
    </div>
  )
}

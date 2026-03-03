import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Card, PageHeader } from '../components/ui'
import { CountdownTimer } from '../components/study/CountdownTimer'
import { useTimedPlan, useRecordReview } from '../hooks/useApi'
import { studyApi, examsApi } from '../api/endpoints'
import type { Flashcard, QuizQuestion, TimedSessionPlan } from '../types'

type Phase = 'setup' | 'studying' | 'summary'
type ItemType = 'card' | 'quiz'

interface StudyItem {
  type: ItemType
  id: string
}

export function TimedStudyPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const timedPlanMutation = useTimedPlan()
  const recordReview = useRecordReview()

  const [phase, setPhase] = useState<Phase>('setup')
  const [minutes, setMinutes] = useState(30)
  const [courseCode, setCourseCode] = useState(searchParams.get('course') || '')
  const [examId] = useState(searchParams.get('exam') || '')

  const [plan, setPlan] = useState<TimedSessionPlan | null>(null)
  const [cards, setCards] = useState<Flashcard[]>([])
  const [quizzes, setQuizzes] = useState<QuizQuestion[]>([])
  const [items, setItems] = useState<StudyItem[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [selectedAnswer, setSelectedAnswer] = useState('')
  const [showQuizAnswer, setShowQuizAnswer] = useState(false)
  const [paused, setPaused] = useState(false)

  // Session stats
  const [cardsReviewed, setCardsReviewed] = useState(0)
  const [quizAnswered, setQuizAnswered] = useState(0)
  const [quizCorrect, setQuizCorrect] = useState(0)

  const currentItem = items[currentIndex]
  const currentCard = currentItem?.type === 'card'
    ? cards.find(c => c.id === currentItem.id) : null
  const currentQuiz = currentItem?.type === 'quiz'
    ? quizzes.find(q => q.id === currentItem.id) : null

  const handleStart = async () => {
    try {
      const result = await timedPlanMutation.mutateAsync({
        minutes,
        course_code: courseCode || undefined,
        exam_id: examId || undefined,
      })
      setPlan(result)

      // Fetch the actual card and quiz data
      const fetchedCards: Flashcard[] = []
      const fetchedQuizzes: QuizQuestion[] = []

      if (result.card_ids.length > 0) {
        const scope = result.course_code || courseCode
        if (scope) {
          const dueCards = await studyApi.due(scope, undefined, result.card_ids.length + 10)
          for (const id of result.card_ids) {
            const card = dueCards.find(c => c.id === id)
            if (card) fetchedCards.push(card)
          }
        }
      }

      if (result.quiz_ids.length > 0) {
        const scope = result.course_code || courseCode
        if (scope) {
          const allQuiz = await import('../api/endpoints').then(m => m.assetsApi.quiz(scope))
          for (const id of result.quiz_ids) {
            const q = allQuiz.find(qq => qq.id === id)
            if (q) fetchedQuizzes.push(q)
          }
        }
      }

      setCards(fetchedCards)
      setQuizzes(fetchedQuizzes)

      // Interleave cards and quizzes
      const studyItems: StudyItem[] = []
      let ci = 0, qi = 0
      while (ci < fetchedCards.length || qi < fetchedQuizzes.length) {
        // 3 cards then 1 quiz pattern
        for (let k = 0; k < 3 && ci < fetchedCards.length; k++, ci++) {
          studyItems.push({ type: 'card', id: fetchedCards[ci].id })
        }
        if (qi < fetchedQuizzes.length) {
          studyItems.push({ type: 'quiz', id: fetchedQuizzes[qi].id })
          qi++
        }
      }

      setItems(studyItems)
      setCurrentIndex(0)
      setPhase('studying')
    } catch {
      // mutation error handled by UI
    }
  }

  const handleTimeUp = useCallback(() => {
    setPhase('summary')
  }, [])

  const handleFinish = useCallback(() => {
    setPhase('summary')
  }, [])

  const advanceItem = useCallback(() => {
    setFlipped(false)
    setSelectedAnswer('')
    setShowQuizAnswer(false)
    if (currentIndex + 1 >= items.length) {
      handleFinish()
    } else {
      setCurrentIndex(prev => prev + 1)
    }
  }, [currentIndex, items.length, handleFinish])

  const handleCardRate = async (quality: number) => {
    if (!currentCard) return
    try {
      await recordReview.mutateAsync({ flashcard_id: currentCard.id, quality })
    } catch { /* best effort */ }
    setCardsReviewed(prev => prev + 1)
    advanceItem()
  }

  const handleQuizSubmit = () => {
    if (!currentQuiz) return
    setShowQuizAnswer(true)
    setQuizAnswered(prev => prev + 1)

    const isCorrect = selectedAnswer.trim().toLowerCase() === currentQuiz.correct_answer.trim().toLowerCase()
    if (isCorrect) setQuizCorrect(prev => prev + 1)

    // Record attempt
    studyApi.quizAttempt({
      quiz_question_id: currentQuiz.id,
      selected_answer: selectedAnswer,
      is_correct: isCorrect,
      exam_id: examId || undefined,
    }).catch(() => { /* best effort */ })
  }

  // Keyboard shortcuts
  useEffect(() => {
    if (phase !== 'studying') return
    const handler = (e: KeyboardEvent) => {
      if (currentItem?.type === 'card') {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault()
          if (!flipped) setFlipped(true)
        }
        if (flipped && e.key >= '0' && e.key <= '5') {
          e.preventDefault()
          handleCardRate(parseInt(e.key))
        }
      }
      if (currentItem?.type === 'quiz' && showQuizAnswer) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          advanceItem()
        }
      }
      if (e.key === 'p') {
        setPaused(prev => !prev)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, currentItem, flipped, showQuizAnswer, advanceItem])

  // Record session on completion
  useEffect(() => {
    if (phase !== 'summary' || !plan) return
    if (examId) {
      examsApi.recordSession(examId, {
        cards_reviewed: cardsReviewed,
        quiz_questions_answered: quizAnswered,
        quiz_correct: quizCorrect,
        duration_seconds: plan.total_minutes * 60,
      }).catch(() => { /* best effort */ })
    }
  }, [phase])

  // ── Setup Phase ──
  if (phase === 'setup') {
    return (
      <div>
        <PageHeader
          title="Timed Study"
          subtitle="Set your available time and start an optimized study session"
        />
        <Card>
          <div className="max-w-md mx-auto space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                How many minutes do you have?
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min={5}
                  max={120}
                  step={5}
                  value={minutes}
                  onChange={e => setMinutes(parseInt(e.target.value))}
                  className="flex-1"
                />
                <span className="text-2xl font-bold text-primary tabular-nums w-16 text-right">
                  {minutes}m
                </span>
              </div>
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>5 min</span>
                <span>120 min</span>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Course (optional)
              </label>
              <input
                type="text"
                placeholder="e.g. CSIT302"
                value={courseCode}
                onChange={e => setCourseCode(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
              />
            </div>

            <button
              onClick={handleStart}
              disabled={timedPlanMutation.isPending}
              className="w-full py-3 bg-primary text-white font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors min-h-[44px]"
            >
              {timedPlanMutation.isPending ? 'Generating plan...' : `Start ${minutes}-minute session`}
            </button>

            {timedPlanMutation.isError && (
              <p className="text-sm text-red-600">
                {timedPlanMutation.error instanceof Error ? timedPlanMutation.error.message : 'Failed to generate plan'}
              </p>
            )}
          </div>
        </Card>
      </div>
    )
  }

  // ── Studying Phase ──
  if (phase === 'studying' && plan) {
    const progress = items.length > 0 ? ((currentIndex) / items.length) * 100 : 0

    return (
      <div>
        <PageHeader title="Timed Study" />

        <div className="space-y-4">
          <CountdownTimer
            totalSeconds={plan.total_minutes * 60}
            onTimeUp={handleTimeUp}
            paused={paused}
          />

          {/* Progress */}
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <span>{currentIndex + 1} / {items.length}</span>
            <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <button
              onClick={() => setPaused(!paused)}
              className="text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-50 min-h-[44px] min-w-[44px] flex items-center justify-center"
            >
              {paused ? 'Resume' : 'Pause'}
            </button>
          </div>

          {/* Current Item */}
          {currentItem?.type === 'card' && currentCard && (
            <Card>
              <div className="text-center py-8">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Flashcard</span>
                <div
                  className="mt-4 cursor-pointer min-h-[200px] flex items-center justify-center"
                  onClick={() => !flipped && setFlipped(true)}
                >
                  {!flipped ? (
                    <div>
                      <p className="text-lg font-medium text-gray-900">{currentCard.front}</p>
                      <p className="text-sm text-gray-400 mt-4">Click or press Space to reveal</p>
                    </div>
                  ) : (
                    <div>
                      <p className="text-lg text-gray-700">{currentCard.back}</p>
                    </div>
                  )}
                </div>
                {flipped && (
                  <div className="mt-6">
                    <p className="text-xs text-gray-400 mb-2">How well did you know this? (0-5)</p>
                    <div className="flex justify-center gap-2">
                      {[0, 1, 2, 3, 4, 5].map(q => (
                        <button
                          key={q}
                          onClick={() => handleCardRate(q)}
                          className={`w-11 h-11 rounded-lg font-medium text-sm transition-colors ${
                            q < 3
                              ? 'bg-red-100 text-red-700 hover:bg-red-200'
                              : q < 4
                                ? 'bg-amber-100 text-amber-700 hover:bg-amber-200'
                                : 'bg-green-100 text-green-700 hover:bg-green-200'
                          }`}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>
          )}

          {currentItem?.type === 'quiz' && currentQuiz && (
            <Card>
              <div className="py-4">
                <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Quiz — {currentQuiz.question_type === 'multiple_choice' ? 'Multiple Choice' : 'Short Answer'}
                </span>
                <p className="text-lg font-medium text-gray-900 mt-3">{currentQuiz.question}</p>

                {currentQuiz.question_type === 'multiple_choice' && currentQuiz.options_json && (
                  <div className="mt-4 space-y-2">
                    {(currentQuiz.options_json as string[]).map((opt, i) => (
                      <button
                        key={i}
                        onClick={() => !showQuizAnswer && setSelectedAnswer(opt.charAt(0))}
                        disabled={showQuizAnswer}
                        className={`w-full text-left px-4 py-3 rounded-lg border text-sm transition-colors min-h-[44px] ${
                          showQuizAnswer
                            ? opt.charAt(0) === currentQuiz.correct_answer
                              ? 'border-green-300 bg-green-50 text-green-800'
                              : selectedAnswer === opt.charAt(0)
                                ? 'border-red-300 bg-red-50 text-red-800'
                                : 'border-gray-200 text-gray-500'
                            : selectedAnswer === opt.charAt(0)
                              ? 'border-primary bg-primary/5 text-primary'
                              : 'border-gray-200 hover:border-gray-300 text-gray-700'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}

                {currentQuiz.question_type === 'short_answer' && (
                  <div className="mt-4">
                    <input
                      type="text"
                      placeholder="Your answer..."
                      value={selectedAnswer}
                      onChange={e => setSelectedAnswer(e.target.value)}
                      disabled={showQuizAnswer}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none disabled:bg-gray-50"
                    />
                  </div>
                )}

                {!showQuizAnswer ? (
                  <button
                    onClick={handleQuizSubmit}
                    disabled={!selectedAnswer}
                    className="mt-4 px-6 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 disabled:opacity-50 transition-colors min-h-[44px]"
                  >
                    Submit Answer
                  </button>
                ) : (
                  <div className="mt-4">
                    {currentQuiz.explanation && (
                      <p className="text-sm text-gray-600 mb-3">{currentQuiz.explanation}</p>
                    )}
                    <button
                      onClick={advanceItem}
                      className="px-6 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors min-h-[44px]"
                    >
                      Next
                    </button>
                  </div>
                )}
              </div>
            </Card>
          )}

          {items.length === 0 && (
            <Card>
              <div className="text-center py-8">
                <p className="text-gray-500">No study material available for this scope.</p>
                <button
                  onClick={() => navigate('/study')}
                  className="mt-4 text-primary text-sm font-medium hover:underline"
                >
                  Go to regular study
                </button>
              </div>
            </Card>
          )}
        </div>
      </div>
    )
  }

  // ── Summary Phase ──
  return (
    <div>
      <PageHeader title="Session Complete" />
      <Card>
        <div className="text-center py-8 space-y-6">
          <div className="text-4xl">
            {quizAnswered > 0 && quizCorrect / quizAnswered >= 0.8 ? '\u2B50' : '\u2705'}
          </div>
          <h2 className="text-xl font-semibold text-gray-900">
            {plan?.total_minutes}-minute session complete
          </h2>
          <div className="grid grid-cols-2 gap-4 max-w-sm mx-auto">
            <div className="bg-blue-50 rounded-lg p-4">
              <p className="text-2xl font-bold text-blue-700">{cardsReviewed}</p>
              <p className="text-xs text-blue-600">Cards reviewed</p>
            </div>
            <div className="bg-purple-50 rounded-lg p-4">
              <p className="text-2xl font-bold text-purple-700">{quizAnswered}</p>
              <p className="text-xs text-purple-600">Quiz questions</p>
            </div>
            {quizAnswered > 0 && (
              <div className="col-span-2 bg-green-50 rounded-lg p-4">
                <p className="text-2xl font-bold text-green-700">
                  {Math.round((quizCorrect / quizAnswered) * 100)}%
                </p>
                <p className="text-xs text-green-600">Quiz accuracy ({quizCorrect}/{quizAnswered})</p>
              </div>
            )}
          </div>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => {
                setPhase('setup')
                setCardsReviewed(0)
                setQuizAnswered(0)
                setQuizCorrect(0)
                setCurrentIndex(0)
                setItems([])
                setPlan(null)
              }}
              className="px-6 py-2 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary/90 transition-colors min-h-[44px]"
            >
              Start another session
            </button>
            <button
              onClick={() => navigate('/')}
              className="px-6 py-2 bg-white text-gray-700 text-sm font-medium rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors min-h-[44px]"
            >
              Back to Dashboard
            </button>
          </div>
        </div>
      </Card>
    </div>
  )
}

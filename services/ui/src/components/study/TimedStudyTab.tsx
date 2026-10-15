import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useSearchParams } from 'react-router-dom'
import { Card, Button, ErrorState, Input, Skeleton } from '../ui'
import { CountdownTimer } from './CountdownTimer'
import { useTimedPlan, useRecordReview } from '../../hooks/useApi'
import { studyApi, examsApi, assetsApi } from '../../api/endpoints'
import { CitationChip } from '../week/CitationChip'
import { PracticeBadge } from '../weakspots/PracticeBadge'
import type { PlanRunState } from '../../lib/planRun'
import { writeQueue } from '../../lib/writeQueue'
import type { Flashcard, QuizQuestion, TimedSessionPlan } from '../../types'

type Phase = 'setup' | 'studying' | 'summary'
type ItemType = 'card' | 'quiz'

interface StudyItem {
  type: ItemType
  id: string
}

interface RunData {
  plan: TimedSessionPlan
  cards: Flashcard[]
  quizzes: QuizQuestion[]
}

/** Resolve a plan's ids to the items to study, looked up per course; ids that no longer resolve are skipped. */
async function fetchRunData(plan: TimedSessionPlan, scopes: string[]): Promise<RunData> {
  const cards: Flashcard[] = []
  const quizzes: QuizQuestion[] = []

  if (plan.card_ids.length > 0) {
    const due: Flashcard[] = []
    for (const scope of scopes) due.push(...(await studyApi.due(scope, undefined, plan.card_ids.length + 10)))
    for (const id of plan.card_ids) {
      const card = due.find(c => c.id === id)
      if (card) cards.push(card)
    }
  }

  if (plan.quiz_ids.length > 0) {
    const all: QuizQuestion[] = []
    for (const scope of scopes) all.push(...(await assetsApi.quiz(scope)))
    for (const id of plan.quiz_ids) {
      const q = all.find(qq => qq.id === id)
      if (q) quizzes.push(q)
    }
  }

  return { plan, cards, quizzes }
}

export function TimedStudyTab() {
  const { t } = useTranslation()

  const [searchParams] = useSearchParams()
  const preset = (useLocation().state as { planRun?: PlanRunState } | null)?.planRun ?? null
  const [presetError, setPresetError] = useState(false)
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

  const [cardsReviewed, setCardsReviewed] = useState(0)
  const [quizAnswered, setQuizAnswered] = useState(0)
  const [quizCorrect, setQuizCorrect] = useState(0)

  const currentItem = items[currentIndex]
  const currentCard = currentItem?.type === 'card'
    ? cards.find(c => c.id === currentItem.id) : null
  const currentQuiz = currentItem?.type === 'quiz'
    ? quizzes.find(q => q.id === currentItem.id) : null

  const beginRun = useCallback((run: RunData) => {
    setPlan(run.plan)
    setCards(run.cards)
    setQuizzes(run.quizzes)

    const studyItems: StudyItem[] = []
    let ci = 0, qi = 0
    while (ci < run.cards.length || qi < run.quizzes.length) {
      for (let k = 0; k < 3 && ci < run.cards.length; k++, ci++) {
        studyItems.push({ type: 'card', id: run.cards[ci].id })
      }
      if (qi < run.quizzes.length) {
        studyItems.push({ type: 'quiz', id: run.quizzes[qi].id })
        qi++
      }
    }

    setItems(studyItems)
    setCurrentIndex(0)
    setPhase('studying')
  }, [])

  const handleStart = async () => {
    try {
      const result = await timedPlanMutation.mutateAsync({
        minutes,
        course_code: courseCode || undefined,
        exam_id: examId || undefined,
      })
      const scope = result.course_code || courseCode
      beginRun(await fetchRunData(result, scope ? [scope] : []))
    } catch {
      // mutation error handled by UI
    }
  }

  // "Study tonight" hands over explicit item ids (api.weak-spots v1): run exactly those.
  const presetStarted = useRef(false)
  const runPreset = useCallback(() => {
    if (!preset) return
    fetchRunData(
      {
        total_minutes: preset.minutes,
        card_ids: preset.cardIds,
        quiz_ids: preset.quizIds,
        estimated_card_minutes: 0,
        estimated_quiz_minutes: 0,
        course_code: null,
        exam_id: null,
      },
      preset.courseCodes,
    ).then(beginRun).catch(() => setPresetError(true))
  }, [preset, beginRun])
  useEffect(() => {
    if (!preset || presetStarted.current) return
    presetStarted.current = true
    runPreset()
  }, [preset, runPreset])

  const handleTimeUp = useCallback(() => setPhase('summary'), [])
  const handleFinish = useCallback(() => setPhase('summary'), [])

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

  const handleCardRate = useCallback(async (quality: number) => {
    if (!currentCard) return
    const review = { flashcard_id: currentCard.id, quality }
    try {
      await recordReview.mutateAsync(review)
    } catch {
      void writeQueue.enqueue({
        url: '/api/study/review',
        method: 'POST',
        body: JSON.stringify(review),
      })
    }
    setCardsReviewed(prev => prev + 1)
    advanceItem()
  }, [currentCard, recordReview, advanceItem])

  const handleQuizSubmit = () => {
    if (!currentQuiz) return
    setShowQuizAnswer(true)
    setQuizAnswered(prev => prev + 1)

    const isCorrect = selectedAnswer.trim().toLowerCase() === currentQuiz.correct_answer.trim().toLowerCase()
    if (isCorrect) setQuizCorrect(prev => prev + 1)

    const attempt = {
      quiz_question_id: currentQuiz.id,
      selected_answer: selectedAnswer,
      is_correct: isCorrect,
      exam_id: examId || undefined,
    }
    studyApi.quizAttempt(attempt).catch(() => {
      void writeQueue.enqueue({
        url: '/api/study/quiz-attempt',
        method: 'POST',
        body: JSON.stringify(attempt),
      })
    })
  }

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
      if (e.key === 'p') setPaused(prev => !prev)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [phase, currentItem, flipped, showQuizAnswer, advanceItem, handleCardRate])

  useEffect(() => {
    if (phase !== 'summary' || !plan) return
    if (examId) {
      const session = {
        cards_reviewed: cardsReviewed,
        quiz_questions_answered: quizAnswered,
        quiz_correct: quizCorrect,
        duration_seconds: plan.total_minutes * 60,
      }
      examsApi.recordSession(examId, session).catch(() => {
        void writeQueue.enqueue({
          url: `/api/exams/${examId}/sessions`,
          method: 'POST',
          body: JSON.stringify(session),
        })
      })
    }
  }, [phase, examId, plan, cardsReviewed, quizAnswered, quizCorrect])

  // ── Tonight's plan loading its items ──
  if (preset && phase === 'setup') {
    return presetError ? (
      <ErrorState
        title={t("Tonight's items couldn't load")}
        onRetry={() => {
          setPresetError(false)
          runPreset()
        }}
      />
    ) : (
      <Card aria-busy="true">
        <Skeleton height={120} />
      </Card>
    )
  }

  // ── Setup Phase ──
  if (phase === 'setup') {
    return (
      <Card className="max-w-md mx-auto">
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-text mb-2">
              {t('How many minutes do you have?')}
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min={5}
                max={120}
                step={5}
                value={minutes}
                onChange={e => setMinutes(parseInt(e.target.value))}
                className="flex-1 accent-sage"
              />
              <span className="text-2xl font-bold text-sage-fg tabular-nums w-16 text-right">
                {minutes}m
              </span>
            </div>
            <div className="flex justify-between text-xs text-text-muted mt-1">
              <span>{t('5 min')}</span>
              <span>{t('120 min')}</span>
            </div>
          </div>

          <Input
            id="timed-course"
            label={t('Course (optional)')}
            placeholder={t('e.g. CSIT302')}
            value={courseCode}
            onChange={e => setCourseCode(e.target.value)}
          />

          <Button
            size="lg"
            className="w-full"
            onClick={handleStart}
            loading={timedPlanMutation.isPending}
          >
            {timedPlanMutation.isPending ? t('Generating plan…') : t('Start {{minutes}}-minute session', { minutes })}
          </Button>

          {timedPlanMutation.isError && (
            <p className="text-sm text-red-fg" role="alert">
              {timedPlanMutation.error instanceof Error ? timedPlanMutation.error.message : t('Failed to generate plan')}
            </p>
          )}
        </div>
      </Card>
    )
  }

  // ── Studying Phase ──
  if (phase === 'studying' && plan) {
    const progress = items.length > 0 ? ((currentIndex) / items.length) * 100 : 0

    return (
      <div className="space-y-4">
        <CountdownTimer
          totalSeconds={plan.total_minutes * 60}
          onTimeUp={handleTimeUp}
          paused={paused}
        />

        <div className="flex items-center gap-3 text-sm text-text-muted">
          <span>{currentIndex + 1} / {items.length}</span>
          <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-sage rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={() => setPaused(!paused)}>
            {paused ? t('Resume') : t('Pause')}
          </Button>
        </div>

        {currentItem?.type === 'card' && currentCard && (
          <Card>
            <div className="text-center py-8">
              <span className="text-xs font-medium text-text-muted uppercase tracking-wider">{t('Flashcard')}</span>
              <span className="ml-2 inline-flex items-center gap-1 align-middle">
                {currentCard.origin === 'targeted' && <PracticeBadge />}
                {currentCard.source_page_ref > 0 && <CitationChip page={currentCard.source_page_ref} />}
              </span>
              <button
                type="button"
                className="mt-4 w-full cursor-pointer min-h-[200px] flex items-center justify-center rounded-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-peri"
                onClick={() => !flipped && setFlipped(true)}
              >
                {!flipped ? (
                  <span className="block">
                    <span className="block text-lg font-medium text-text">{currentCard.front}</span>
                    <span className="block text-sm text-text-muted mt-4">{t('Click or press Space to reveal')}</span>
                  </span>
                ) : (
                  <span className="block text-lg text-text">{currentCard.back}</span>
                )}
              </button>
              {flipped && (
                <div className="mt-6">
                  <p className="text-xs text-text-muted mb-2">{t('How well did you know this? (0-5)')}</p>
                  <div className="flex justify-center gap-2">
                    {[0, 1, 2, 3, 4, 5].map(q => (
                      <button
                        key={q}
                        onClick={() => handleCardRate(q)}
                        className={`w-11 h-11 rounded-lg font-medium text-sm transition-colors ${
                          q < 3
                            ? 'bg-red-soft text-red-fg hover:bg-red/25'
                            : q < 4
                              ? 'bg-amber-soft text-amber-fg hover:bg-amber/25'
                              : 'bg-sage-soft text-sage-fg hover:bg-sage/25'
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
              <span className="text-xs font-medium text-text-muted uppercase tracking-wider">
                {currentQuiz.question_type === 'multiple_choice'
                      ? t('Quiz — Multiple Choice')
                      : t('Quiz — Short Answer')}
              </span>
              <span className="ml-2 inline-flex items-center gap-1 align-middle">
                {currentQuiz.origin === 'targeted' && <PracticeBadge />}
                {currentQuiz.source_page_ref > 0 && <CitationChip page={currentQuiz.source_page_ref} />}
              </span>
              <p className="text-lg font-medium text-text mt-3">{currentQuiz.question}</p>

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
                            ? 'border-sage/40 bg-sage-soft text-sage-fg'
                            : selectedAnswer === opt.charAt(0)
                              ? 'border-red/40 bg-red-soft text-red-fg'
                              : 'border-border text-text-muted'
                          : selectedAnswer === opt.charAt(0)
                            ? 'border-sage bg-sage-soft text-sage-fg'
                            : 'border-border hover:border-text-muted text-text'
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}

              {currentQuiz.question_type === 'short_answer' && (
                <div className="mt-4">
                  <Input
                    id="timed-short-answer"
                    placeholder={t('Your answer…')}
                    value={selectedAnswer}
                    onChange={e => setSelectedAnswer(e.target.value)}
                    disabled={showQuizAnswer}
                  />
                </div>
              )}

              {!showQuizAnswer ? (
                <Button className="mt-4" onClick={handleQuizSubmit} disabled={!selectedAnswer}>
                  {t('Submit answer')}
                </Button>
              ) : (
                <div className="mt-4">
                  {currentQuiz.explanation && (
                    <p className="text-sm text-text-muted mb-3">{currentQuiz.explanation}</p>
                  )}
                  <Button onClick={advanceItem}>{t('Next')}</Button>
                </div>
              )}
            </div>
          </Card>
        )}

        {items.length === 0 && (
          <Card>
            <div className="text-center py-8">
              <p className="text-text-muted">{t('No study material available for this scope.')}</p>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // ── Summary Phase ──
  return (
    <Card>
      <div className="text-center py-8 space-y-6">
        <div className="text-4xl">
          {quizAnswered > 0 && quizCorrect / quizAnswered >= 0.8 ? '\u2B50' : '\u2705'}
        </div>
        <h2 className="text-xl font-semibold text-text">
          {t('{{minutes}}-minute session complete', { minutes: plan?.total_minutes })}
        </h2>
        <div className="grid grid-cols-2 gap-4 max-w-sm mx-auto">
          <div className="bg-peri-soft rounded-lg p-4">
            <p className="text-2xl font-bold text-peri-fg">{cardsReviewed}</p>
            <p className="text-xs text-peri-fg/80">{t('Cards reviewed')}</p>
          </div>
          <div className="bg-amber-soft rounded-lg p-4">
            <p className="text-2xl font-bold text-amber-fg">{quizAnswered}</p>
            <p className="text-xs text-amber-fg/80">{t('Quiz questions')}</p>
          </div>
          {quizAnswered > 0 && (
            <div className="col-span-2 bg-sage-soft rounded-lg p-4">
              <p className="text-2xl font-bold text-sage-fg">
                {Math.round((quizCorrect / quizAnswered) * 100)}%
              </p>
              <p className="text-xs text-sage-fg/80">{t('Quiz accuracy ({{correct}}/{{answered}})', { correct: quizCorrect, answered: quizAnswered })}</p>
            </div>
          )}
        </div>
        <div className="flex justify-center gap-3">
          <Button
            onClick={() => {
              setPhase('setup')
              setCardsReviewed(0)
              setQuizAnswered(0)
              setQuizCorrect(0)
              setCurrentIndex(0)
              setItems([])
              setPlan(null)
            }}
          >
            {t('Start another session')}
          </Button>
        </div>
      </div>
    </Card>
  )
}

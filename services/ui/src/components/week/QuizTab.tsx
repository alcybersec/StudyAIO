import { useState, useMemo } from 'react'
import { useQuizQuestions, useRecordQuizAttempt } from '../../hooks/useApi'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { EmptyState, ErrorState, Skeleton } from '../ui'
import type { QuizQuestion } from '../../types'

interface QuizTabProps {
  courseCode: string
  week: number
  examId?: string
}

function MCQOptions({
  question,
  onAnswer,
}: {
  question: QuizQuestion
  onAnswer: (correct: boolean) => void
}) {
  const [selected, setSelected] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  const options = question.options_json ?? []
  const isCorrect = selected === question.correct_answer

  function handleSubmit() {
    if (!selected) return
    setSubmitted(true)
    onAnswer(selected === question.correct_answer)
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {options.map((opt) => {
          const optLetter = opt.charAt(0)
          const isSelected = selected === optLetter
          const isRight = submitted && optLetter === question.correct_answer
          const isWrong = submitted && isSelected && !isCorrect

          return (
            <label
              key={opt}
              className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                isRight
                  ? 'border-sage/40 bg-sage-soft'
                  : isWrong
                    ? 'border-red/40 bg-red-soft'
                    : isSelected
                      ? 'border-peri bg-peri-soft'
                      : 'border-border hover:border-border-strong'
              } ${submitted ? 'pointer-events-none' : ''}`}
            >
              <input
                type="radio"
                name={question.id}
                value={optLetter}
                checked={isSelected}
                onChange={() => setSelected(optLetter)}
                disabled={submitted}
                className="mt-0.5 accent-[var(--color-sage)]"
              />
              <span className="text-sm text-text">{opt}</span>
            </label>
          )
        })}
      </div>

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!selected}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          Submit
        </button>
      )}

      {submitted && (
        <div
          className={`p-3 rounded-lg text-sm ${
            isCorrect ? 'bg-sage-soft text-sage-fg' : 'bg-red-soft text-red-fg'
          }`}
        >
          <span className="font-medium">{isCorrect ? 'Correct!' : 'Incorrect.'}</span>{' '}
          <span className="text-text-muted">{question.explanation}</span>
        </div>
      )}
    </div>
  )
}

function ShortAnswer({
  question,
  onAnswer,
}: {
  question: QuizQuestion
  onAnswer: (correct: boolean) => void
}) {
  const [answer, setAnswer] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [selfAssessed, setSelfAssessed] = useState<boolean | null>(null)

  function handleSubmit() {
    if (!answer.trim()) return
    setSubmitted(true)
  }

  function handleSelfAssess(correct: boolean) {
    setSelfAssessed(correct)
    onAnswer(correct)
  }

  return (
    <div className="space-y-3">
      <textarea
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        disabled={submitted}
        placeholder="Type your answer..."
        rows={3}
        className="w-full p-3 rounded-lg border border-border bg-surface-1 text-sm text-text placeholder:text-text-faint focus:outline-none focus:border-peri disabled:bg-surface-2 disabled:opacity-70"
      />

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!answer.trim()}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          Submit
        </button>
      )}

      {submitted && (
        <>
          <div className="p-3 rounded-lg bg-peri-soft text-sm text-peri-fg">
            <span className="font-medium">Model answer:</span>{' '}
            <span className="text-text">{question.correct_answer}</span>
          </div>
          <div className="p-3 rounded-lg bg-surface-2 text-sm text-text-muted">
            {question.explanation}
          </div>

          {selfAssessed === null && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-text-muted">How did you do?</span>
              <button
                onClick={() => handleSelfAssess(true)}
                className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-sage-soft text-sage-fg hover:opacity-80 transition-opacity cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
              >
                Correct
              </button>
              <button
                onClick={() => handleSelfAssess(false)}
                className="px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-red-soft text-red-fg hover:opacity-80 transition-opacity cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
              >
                Incorrect
              </button>
            </div>
          )}

          {selfAssessed !== null && (
            <div
              className={`text-sm font-medium ${selfAssessed ? 'text-sage-fg' : 'text-red-fg'}`}
            >
              Marked as {selfAssessed ? 'correct' : 'incorrect'}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function QuizSkeleton() {
  return (
    <div className="space-y-6 py-4" aria-busy="true">
      <div className="flex items-center justify-between">
        <Skeleton width={140} height={16} />
        <Skeleton width={80} height={10} />
      </div>
      <Skeleton width="70%" height={20} />
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} height={46} />
        ))}
      </div>
    </div>
  )
}

export function QuizTab({ courseCode, week, examId }: QuizTabProps) {
  const { data: questions, isLoading, error, refetch } = useQuizQuestions(courseCode, week)
  const recordAttempt = useRecordQuizAttempt()
  const online = useOnlineStatus()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, boolean>>({})
  const [finished, setFinished] = useState(false)

  const total = questions?.length ?? 0
  const question = questions?.[currentIndex]

  const correctCount = useMemo(
    () => Object.values(answers).filter(Boolean).length,
    [answers],
  )

  function handleAnswer(correct: boolean) {
    setAnswers((prev) => ({ ...prev, [currentIndex]: correct }))
    // Record attempt to backend
    const q = questions?.[currentIndex]
    if (q) {
      recordAttempt.mutate({
        quiz_question_id: q.id,
        selected_answer: correct ? q.correct_answer : 'incorrect',
        is_correct: correct,
        exam_id: examId,
      })
    }
  }

  function goToNext() {
    if (currentIndex < total - 1) {
      setCurrentIndex((i) => i + 1)
    } else {
      setFinished(true)
    }
  }

  function restart() {
    setCurrentIndex(0)
    setAnswers({})
    setFinished(false)
  }

  if (error) {
    return (
      <ErrorState
        title={online ? "The quiz couldn't load" : "You're offline"}
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!questions && !online) {
    return (
      <ErrorState
        title="You're offline"
        detail="Quiz questions for this week haven't been cached. They'll load once you're back online."
        onRetry={() => refetch()}
      />
    )
  }
  if (isLoading || !questions) return <QuizSkeleton />
  if (!total) {
    return (
      <EmptyState
        title="No quiz questions yet"
        description="Quiz questions will be generated when the pipeline processes lecture files."
      />
    )
  }

  if (finished) {
    const pct = Math.round((correctCount / total) * 100)
    return (
      <div className="flex flex-col items-center gap-6 py-8">
        <div className="text-5xl font-bold text-text">{pct}%</div>
        <div className="text-lg text-text-muted">
          {correctCount} / {total} correct
        </div>
        <div
          className={`text-sm font-medium ${pct >= 70 ? 'text-sage-fg' : 'text-amber-fg'}`}
        >
          {pct >= 90
            ? 'Excellent!'
            : pct >= 70
              ? 'Good job!'
              : 'Keep studying!'}
        </div>
        <button
          onClick={restart}
          className="px-5 py-2.5 rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          Restart Quiz
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 py-4">
      {/* Progress */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-muted font-mono font-medium">
          Question {currentIndex + 1} / {total}
        </span>
        <div className="flex items-center gap-1" aria-hidden>
          {Array.from({ length: total }, (_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i === currentIndex
                  ? 'bg-peri'
                  : i in answers
                    ? answers[i]
                      ? 'bg-sage'
                      : 'bg-red'
                    : 'bg-surface-2'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Question */}
      <div className="text-base font-medium text-text">{question!.question}</div>

      {/* Answer area */}
      {question!.question_type === 'multiple_choice' ? (
        <MCQOptions
          key={question!.id}
          question={question!}
          onAnswer={handleAnswer}
        />
      ) : (
        <ShortAnswer
          key={question!.id}
          question={question!}
          onAnswer={handleAnswer}
        />
      )}

      {/* Next button (shown after answering) */}
      {currentIndex in answers && (
        <div className="flex justify-end">
          <button
            onClick={goToNext}
            className="px-4 py-2 rounded-lg text-sm font-medium bg-surface-2 text-text border border-border hover:border-border-strong transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
          >
            {currentIndex === total - 1 ? 'Finish' : 'Next'}
          </button>
        </div>
      )}
    </div>
  )
}

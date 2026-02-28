import { useState, useMemo } from 'react'
import { useQuizQuestions } from '../../hooks/useApi'
import { LoadingSpinner, EmptyState } from '../ui'
import type { QuizQuestion } from '../../types'

interface QuizTabProps {
  courseCode: string
  week: number
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
                  ? 'border-green-300 bg-green-50'
                  : isWrong
                    ? 'border-red-300 bg-red-50'
                    : isSelected
                      ? 'border-primary bg-primary/5'
                      : 'border-gray-200 hover:border-gray-300'
              } ${submitted ? 'pointer-events-none' : ''}`}
            >
              <input
                type="radio"
                name={question.id}
                value={optLetter}
                checked={isSelected}
                onChange={() => setSelected(optLetter)}
                disabled={submitted}
                className="mt-0.5"
              />
              <span className="text-sm text-gray-700">{opt}</span>
            </label>
          )
        })}
      </div>

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!selected}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Submit
        </button>
      )}

      {submitted && (
        <div
          className={`p-3 rounded-lg text-sm ${
            isCorrect ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
          }`}
        >
          <span className="font-medium">{isCorrect ? 'Correct!' : 'Incorrect.'}</span>{' '}
          {question.explanation}
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
        className="w-full p-3 rounded-lg border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:bg-gray-50"
      />

      {!submitted && (
        <button
          onClick={handleSubmit}
          disabled={!answer.trim()}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Submit
        </button>
      )}

      {submitted && (
        <>
          <div className="p-3 rounded-lg bg-blue-50 text-sm text-blue-800">
            <span className="font-medium">Model answer:</span> {question.correct_answer}
          </div>
          <div className="p-3 rounded-lg bg-gray-50 text-sm text-gray-600">
            {question.explanation}
          </div>

          {selfAssessed === null && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">How did you do?</span>
              <button
                onClick={() => handleSelfAssess(true)}
                className="px-3 py-1.5 rounded-lg text-sm font-medium bg-green-100 text-green-700 hover:bg-green-200 transition-colors"
              >
                Correct
              </button>
              <button
                onClick={() => handleSelfAssess(false)}
                className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
              >
                Incorrect
              </button>
            </div>
          )}

          {selfAssessed !== null && (
            <div
              className={`text-sm font-medium ${selfAssessed ? 'text-green-600' : 'text-red-600'}`}
            >
              Marked as {selfAssessed ? 'correct' : 'incorrect'}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export function QuizTab({ courseCode, week }: QuizTabProps) {
  const { data: questions, isLoading, error } = useQuizQuestions(courseCode, week)
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

  if (isLoading) return <LoadingSpinner label="Loading quiz..." />
  if (error) return <EmptyState icon="!" title="Failed to load quiz" />
  if (!total) {
    return (
      <EmptyState
        icon="?"
        title="No quiz questions yet"
        description="Quiz questions will be generated when the pipeline processes lecture files."
      />
    )
  }

  if (finished) {
    const pct = Math.round((correctCount / total) * 100)
    return (
      <div className="flex flex-col items-center gap-6 py-8">
        <div className="text-5xl font-bold text-gray-800">{pct}%</div>
        <div className="text-lg text-gray-600">
          {correctCount} / {total} correct
        </div>
        <div
          className={`text-sm font-medium ${pct >= 70 ? 'text-green-600' : 'text-amber-600'}`}
        >
          {pct >= 90
            ? 'Excellent!'
            : pct >= 70
              ? 'Good job!'
              : 'Keep studying!'}
        </div>
        <button
          onClick={restart}
          className="px-5 py-2.5 rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors"
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
        <span className="text-gray-500 font-medium">
          Question {currentIndex + 1} / {total}
        </span>
        <div className="flex items-center gap-1">
          {Array.from({ length: total }, (_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full ${
                i === currentIndex
                  ? 'bg-primary'
                  : i in answers
                    ? answers[i]
                      ? 'bg-green-400'
                      : 'bg-red-400'
                    : 'bg-gray-200'
              }`}
            />
          ))}
        </div>
      </div>

      {/* Question */}
      <div className="text-base font-medium text-gray-800">{question!.question}</div>

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
            className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
          >
            {currentIndex === total - 1 ? 'Finish' : 'Next'}
          </button>
        </div>
      )}
    </div>
  )
}

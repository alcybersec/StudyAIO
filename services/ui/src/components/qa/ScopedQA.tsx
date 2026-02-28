import { useState } from 'react'
import { useAskQuestion } from '../../hooks/useApi'
import { Card, EmptyState } from '../ui'
import { QuestionForm } from './QuestionForm'
import { AnswerDisplay } from './AnswerDisplay'
import type { QAExchange } from '../../types'

interface ScopedQAProps {
  courseCode: string
  week: number
}

export function ScopedQA({ courseCode, week }: ScopedQAProps) {
  const askMutation = useAskQuestion()
  const [history, setHistory] = useState<QAExchange[]>([])

  const handleAsk = (question: string) => {
    askMutation.mutate(
      { question, course_code: courseCode, week },
      {
        onSuccess: (response) => {
          setHistory((prev) => [
            {
              question,
              response,
              timestamp: new Date().toISOString(),
            },
            ...prev,
          ])
        },
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="bg-primary/5 rounded-lg px-4 py-2 text-sm text-gray-600">
        Questions are scoped to <span className="font-medium">{courseCode} Week {week}</span>
      </div>

      <QuestionForm
        courses={[]}
        onSubmit={handleAsk}
        isLoading={askMutation.isPending}
        defaultCourseCode={courseCode}
        defaultWeek={week}
      />

      {/* Loading */}
      {askMutation.isPending && (
        <div className="flex items-center gap-3 text-gray-500 py-4">
          <div className="animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full" />
          <span className="text-sm">Searching and generating answer...</span>
        </div>
      )}

      {/* Error */}
      {askMutation.isError && (
        <div className="border border-red-200 bg-red-50 rounded-lg p-3">
          <p className="text-sm text-red-700">
            {(askMutation.error as Error).message}
          </p>
        </div>
      )}

      {/* History */}
      {history.length > 0 ? (
        <div className="space-y-4">
          {history.map((exchange, i) => (
            <Card key={i}>
              <p className="text-sm font-medium text-gray-900 mb-2">{exchange.question}</p>
              <AnswerDisplay
                answer={exchange.response.answer}
                citations={exchange.response.citations}
                chunksSearched={exchange.response.chunks_searched}
              />
            </Card>
          ))}
        </div>
      ) : (
        !askMutation.isPending && (
          <EmptyState
            icon="?"
            title="Ask about this week"
            description={`Ask any question about ${courseCode} Week ${week} content.`}
          />
        )
      )}
    </div>
  )
}

import { useState } from 'react'
import { useAskQuestion, useCourses } from '../hooks/useApi'
import { PageHeader, Card, EmptyState } from '../components/ui'
import { QuestionForm } from '../components/qa/QuestionForm'
import { AnswerDisplay } from '../components/qa/AnswerDisplay'
import type { QAExchange } from '../types'

export function QAPage() {
  const { data: courses } = useCourses()
  const askMutation = useAskQuestion()
  const [history, setHistory] = useState<QAExchange[]>([])

  const handleAsk = (question: string, courseCode?: string, week?: number) => {
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
    <div>
      <PageHeader
        title="Q&A"
        subtitle="Ask questions about your lecture materials"
        breadcrumbs={[{ label: 'Dashboard', to: '/' }, { label: 'Q&A' }]}
      />

      {/* Question form */}
      <Card className="mb-6">
        <QuestionForm
          courses={courses ?? []}
          onSubmit={handleAsk}
          isLoading={askMutation.isPending}
        />
      </Card>

      {/* Loading state */}
      {askMutation.isPending && (
        <Card className="mb-4">
          <div className="flex items-center gap-3 text-gray-500">
            <div className="animate-spin w-5 h-5 border-2 border-primary border-t-transparent rounded-full" />
            <span className="text-sm">Searching lectures and generating answer...</span>
          </div>
        </Card>
      )}

      {/* Error state */}
      {askMutation.isError && (
        <Card className="mb-4 border-red-200 bg-red-50">
          <p className="text-sm text-red-700">
            Failed to get answer: {(askMutation.error as Error).message}
          </p>
        </Card>
      )}

      {/* Session history */}
      {history.length > 0 ? (
        <div className="space-y-4">
          {history.map((exchange, i) => (
            <Card key={i}>
              <div className="mb-3">
                <p className="text-sm font-medium text-gray-900">{exchange.question}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {new Date(exchange.timestamp).toLocaleTimeString()}
                </p>
              </div>
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
            title="No questions yet"
            description="Ask a question above to search your lecture materials."
          />
        )
      )}
    </div>
  )
}

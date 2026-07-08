import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { Card, EmptyState, ErrorState, SectionLabel, Select, Skeleton } from '../ui'
import { useCourses, useExamReadiness, useExams } from '../../hooks/useApi'
import { accuracyTextVar, accuracyToneVar, isWeakTopic } from './readiness'
import type { ReadinessTopic } from '../../types'

function daysOut(examDate: string): number {
  return Math.ceil((new Date(examDate).getTime() - Date.now()) / 86400000)
}

function TopicRow({ topic, studyHref }: { topic: ReadinessTopic; studyHref: string | null }) {
  const weak = isWeakTopic(topic.accuracy)
  return (
    <div className="flex items-center gap-3 py-2 text-[13px]" role="row">
      <span className="flex-1 min-w-0 truncate font-medium text-text" role="cell">
        {topic.topic}
      </span>
      <span className="font-mono text-[10px] text-text-faint w-10 shrink-0" role="cell">
        wk {topic.week}
      </span>
      <span className="w-24 h-1 bg-surface-2 rounded-full overflow-hidden shrink-0" aria-hidden>
        {topic.accuracy !== null && (
          <span
            data-testid={`accuracy-bar-${topic.topic}`}
            className="block h-full rounded-full"
            style={{ width: `${topic.accuracy}%`, background: accuracyToneVar(topic.accuracy) }}
          />
        )}
      </span>
      <span
        className="font-mono text-xs w-9 text-right shrink-0"
        style={{ color: accuracyTextVar(topic.accuracy) }}
        role="cell"
      >
        {topic.accuracy !== null ? `${Math.round(topic.accuracy)}%` : '—'}
      </span>
      <span className="w-24 shrink-0 text-right" role="cell">
        {weak && studyHref && (
          <Link
            to={studyHref}
            className="inline-flex items-center gap-1 text-xs font-medium text-text-muted hover:text-text px-2 py-1 rounded-md hover:bg-surface-2 transition-colors"
          >
            Study now <ArrowRight size={12} aria-hidden />
          </Link>
        )}
      </span>
    </div>
  )
}

/**
 * Readiness drill-down — overall readiness bar plus a dense per-topic table
 * wired to `GET /api/exams/{id}/readiness`.
 */
export function ReadinessDrilldown() {
  const [pickedExamId, setPickedExamId] = useState('')
  const { data: exams, isLoading: examsLoading, error: examsError, refetch: refetchExams } = useExams(undefined, 'active')
  const { data: courses } = useCourses()

  const activeExamId = pickedExamId || exams?.[0]?.id || ''
  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useExamReadiness(activeExamId)

  const exam = exams?.find((e) => e.id === activeExamId)
  const courseCode = courses?.find((c) => c.id === exam?.course_id)?.code ?? null

  const sortedTopics = useMemo(() => {
    if (!detail?.topics) return []
    return [...detail.topics].sort((a, b) => {
      const av = a.accuracy ?? -1
      const bv = b.accuracy ?? -1
      return av - bv
    })
  }, [detail])

  if (examsLoading || (activeExamId && detailLoading)) {
    return (
      <Card padding>
        <Skeleton height={14} width={192} className="mb-3" />
        <Skeleton height={6} width="100%" className="mb-4" />
        <div className="space-y-2.5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} height={20} width="100%" />
          ))}
        </div>
      </Card>
    )
  }

  if (examsError || detailError) {
    return (
      <ErrorState
        title="Readiness couldn't load"
        detail={String(examsError ?? detailError)}
        onRetry={() => (examsError ? refetchExams() : refetchDetail())}
      />
    )
  }

  if (!exams || exams.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="🎯"
          title="No active exams"
          description="Create an exam to see a topic-level readiness breakdown of the weeks in scope."
          actionLabel="Set up an exam"
          actionTo="/study?tab=exams"
        />
      </Card>
    )
  }

  if (!detail) return null

  const remaining = exam ? daysOut(exam.exam_date) : null

  return (
    <Card padding>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <SectionLabel className="mb-0">
          Exam readiness — {detail.title} · {detail.overall}%
        </SectionLabel>
        <div className="flex items-center gap-3">
          {remaining !== null && remaining >= 0 && (
            <span className="font-mono text-[10px] text-text-faint shrink-0">
              {remaining} day{remaining === 1 ? '' : 's'} out
            </span>
          )}
          {exams.length > 1 && (
            <Select
              className="w-44"
              options={exams.map((e) => ({ value: e.id, label: e.title }))}
              value={activeExamId}
              onValueChange={setPickedExamId}
            />
          )}
        </div>
      </div>

      <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden mt-2 mb-3">
        <div className="h-full bg-sage rounded-full" style={{ width: `${detail.overall}%` }} />
      </div>

      {sortedTopics.length === 0 ? (
        <p className="text-sm text-text-muted py-4">No topics in this exam's scope yet.</p>
      ) : (
        <div className="divide-y divide-border" role="table" aria-label="Per-topic mastery">
          {sortedTopics.map((topic) => (
            <TopicRow
              key={`${topic.week}-${topic.topic}`}
              topic={topic}
              studyHref={
                courseCode ? `/study?tab=flashcards&course=${courseCode}&week=${topic.week}` : null
              }
            />
          ))}
        </div>
      )}

      <p className="font-mono text-[11px] text-text-faint mt-3">
        readiness = weighted topic mastery × coverage · weak rows link to a scoped session
      </p>
    </Card>
  )
}

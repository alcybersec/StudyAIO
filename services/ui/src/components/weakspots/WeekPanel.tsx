import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { Button, Card } from '../ui'
import { useDiagnostic } from '../../hooks/useWeakSpots'
import { userErrorMessage } from '../../lib/userError'
import { diagnosticRun, masteryLabel, masteryState } from '../../lib/weakSpots'
import type { WeakSpotCourse, WeakSpotWeek } from '../../types'
import { PracticeRequest } from './PracticeRequest'

interface WeekPanelProps {
  course: WeakSpotCourse
  week: WeakSpotWeek
}

/** Detail for one selected cell: evidence, the diagnostic entry for unknown weeks, and "practise". */
export function WeekPanel({ course, week }: WeekPanelProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const diagnostic = useDiagnostic()
  const state = masteryState(week.status)
  const e = week.evidence
  const summary = [masteryLabel(state)]
  if (week.weakness != null) summary.push(t('weakness {{pct}}%', { pct: Math.round(week.weakness * 100) }))
  if (week.next_exam) summary.push(t('exam in {{days}}d', { days: week.next_exam.days_to_exam }))

  const startDiagnostic = () => {
    diagnostic.mutate(
      { courseId: course.course_id, week: week.week },
      {
        onSuccess: (d) => {
          if (d.question_ids.length === 0) return
          navigate('/study?tab=timed', { state: { planRun: diagnosticRun(d, course.course_code) } })
        },
      },
    )
  }

  const needsGeneration = diagnostic.data?.needs_generation === true
  const noQuestions = diagnostic.isSuccess && diagnostic.data.question_ids.length === 0

  return (
    <Card>
      <section aria-labelledby="week-panel-title" className="space-y-3">
        <div>
          <h3 id="week-panel-title" className="text-sm font-semibold text-text">
            {course.course_code} · {t('Week {{week}}', { week: week.week })}
          </h3>
          <p className="text-xs text-text-muted">
            {summary.join(' · ')}
          </p>
        </div>

        <p className="text-xs text-text-muted">
          {t('{{attempts}} quiz answers, {{cards}} cards reviewed', {
            attempts: e.quiz_attempts,
            cards: e.cards_reviewed,
          })}
        </p>

        {state === 'unknown' && (
          <div className="space-y-2">
            <p className="text-xs text-text-muted">
              {t("There isn't enough to judge this week yet. A short check-in uses questions you already have.")}
            </p>
            <Button
              size="sm"
              variant="secondary"
              className="min-h-[44px] md:min-h-0"
              onClick={startDiagnostic}
              loading={diagnostic.isPending}
            >
              {t('Start a short check-in')}
            </Button>
            {diagnostic.isError && (
              <p role="alert" className="text-xs text-red-fg">
                {userErrorMessage(diagnostic.error, t("Couldn't load the check-in"))}
              </p>
            )}
            {(needsGeneration || noQuestions) && (
              <p role="status" className="text-xs text-text-muted">
                {noQuestions
                  ? t("This week has no questions yet. Practise it below to generate some.")
                  : t('This week has few questions, so the check-in is short. You can generate more below.')}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-3">
          <PracticeRequest
            key={`${course.course_id}:${week.week}:quiz`}
            courseId={course.course_id}
            week={week.week}
            kind="quiz"
            label={t('Practise this week: questions')}
          />
          <PracticeRequest
            key={`${course.course_id}:${week.week}:flashcards`}
            courseId={course.course_id}
            week={week.week}
            kind="flashcards"
            label={t('Practise this week: flashcards')}
            variant="secondary"
          />
        </div>
      </section>
    </Card>
  )
}

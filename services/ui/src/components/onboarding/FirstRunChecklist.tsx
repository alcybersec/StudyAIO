import { useContext } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useCourseDetail, useDashboard } from '../../hooks/useApi'
import { useDiagnostic, useWeakSpots } from '../../hooks/useWeakSpots'
import { useOnboardingState } from '../../hooks/useOnboardingState'
import { useConsent } from '../../contexts/consentContext'
import { PipelineEventsContext } from '../../contexts/pipelineProgress'
import { PIPELINE_STAGE_NAMES } from '../../lib/pipelineStages'
import { userErrorMessage } from '../../lib/userError'
import { diagnosticRun } from '../../lib/weakSpots'
import {
  deriveOnboarding,
  firstCourseWithMaterial,
  firstSummaryTarget,
  hasStudyEvidence,
} from '../../lib/onboarding'
import { Card } from '../ui'
import { ChecklistStep, STEP_ACTION_CLASS } from './ChecklistStep'

/**
 * Dashboard first-run flow: upload -> first summary -> diagnostic check-in.
 * Derived entirely from queries the dashboard already uses; the only state it
 * owns is the per-user dismissal in localStorage. Renders nothing until the
 * data is in, so a returning user never sees it flash.
 */
export function FirstRunChecklist() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { requestConsent } = useConsent()
  const onboarding = useOnboardingState()
  const pipeline = useContext(PipelineEventsContext)

  const { data: dashboard } = useDashboard()
  const course = firstCourseWithMaterial(dashboard?.courses)
  const { data: detail } = useCourseDetail(course?.code ?? '')
  const { data: weakSpots } = useWeakSpots()
  const diagnostic = useDiagnostic()

  const summaryTarget = firstSummaryTarget(detail)
  const activeUploads = pipeline?.activeCount ?? 0
  const state = deriveOnboarding({
    courses: dashboard?.courses,
    recentActivity: dashboard?.recent_activity,
    trackedUploads: pipeline?.uploads.length ?? 0,
    activeUploads,
    summaryTarget,
    summaryRead: onboarding.summaryRead,
    checkInDone: hasStudyEvidence(weakSpots),
  })

  const visible = onboarding.ready && !onboarding.dismissed && (state.phase !== 'done' || onboarding.reopened)
  if (!dashboard || !weakSpots || !visible) return null

  const consentRequired = !!user?.ai_consent_required
  const latest = pipeline?.events.at(-1)
  const stageNo = latest ? PIPELINE_STAGE_NAMES.indexOf(latest.stage as (typeof PIPELINE_STAGE_NAMES)[number]) + 1 : 0

  const agreeThenUpload = () => {
    void requestConsent().then((ok) => {
      if (ok) navigate('/upload')
    })
  }
  const startCheckIn = () => {
    if (!summaryTarget) return
    diagnostic.mutate(
      { courseId: summaryTarget.courseId, week: summaryTarget.week },
      {
        onSuccess: (d) => {
          if (d.question_ids.length === 0) return
          navigate('/study?tab=timed', { state: { planRun: diagnosticRun(d, summaryTarget.courseCode) } })
        },
      },
    )
  }
  const noQuestions = diagnostic.isSuccess && diagnostic.data.question_ids.length === 0
  const weekPath = summaryTarget ? `/courses/${summaryTarget.courseCode}/weeks/${summaryTarget.week}` : '/'

  return (
    <Card className="mb-4">
      <section aria-labelledby="first-run-title">
        <h2 id="first-run-title" className="text-sm font-semibold text-text">
          {t('Get started')}
        </h2>
        <p className="text-xs text-text-muted mt-0.5">
          {t('Three steps to your first exam-ready study material.')}
        </p>

        <ol className="divide-y divide-border mt-2">
          <ChecklistStep index={1} title={t('Upload your first lecture')} status={state.upload}>
            {state.upload === 'active' && consentRequired && (
              <>
                <p className="text-xs text-text-muted">
                  {t('Summaries are written by an AI provider, so your lecture text is sent to it. Review how your data is used and agree before your first upload.')}
                </p>
                <button type="button" className={STEP_ACTION_CLASS} onClick={agreeThenUpload}>
                  {t('Review and agree')}
                </button>
              </>
            )}
            {state.upload === 'active' && !consentRequired && (
              <>
                <p className="text-xs text-text-muted">{t('PDF, DOCX or PPTX. The course and week are detected for you.')}</p>
                <Link to="/upload" className={STEP_ACTION_CLASS}>
                  {t('Upload a lecture')}
                </Link>
              </>
            )}
            {state.upload === 'done' && activeUploads > 0 && (
              <p role="status" className="text-xs text-text-muted">
                {stageNo > 0
                  ? t('Processing your lecture: stage {{current}} of {{total}}', {
                      current: stageNo,
                      total: PIPELINE_STAGE_NAMES.length,
                    })
                  : t('Processing your lecture')}
              </p>
            )}
          </ChecklistStep>

          <ChecklistStep index={2} title={t('Read your first summary')} status={state.summary}>
            {state.summary === 'locked' && (
              <p className="text-xs text-text-muted">{t('Ready a minute or two after your upload finishes.')}</p>
            )}
            {state.summary !== 'locked' && (
              <Link to={weekPath} className={STEP_ACTION_CLASS} onClick={onboarding.markSummaryRead}>
                {t('Open summary')}
              </Link>
            )}
          </ChecklistStep>

          <ChecklistStep index={3} title={t('Take a short check-in')} status={state.checkIn}>
            <p className="text-xs text-text-muted">
              {t('A few questions on that week show what to practise first.')}
            </p>
            {state.checkIn === 'active' && (
              <button type="button" className={STEP_ACTION_CLASS} onClick={startCheckIn} disabled={diagnostic.isPending}>
                {t('Start the check-in')}
              </button>
            )}
            {diagnostic.isError && (
              <p role="alert" className="text-xs text-red-fg">
                {userErrorMessage(diagnostic.error, t("Couldn't load the check-in"))}
              </p>
            )}
            {noQuestions && (
              <p role="status" className="text-xs text-text-muted">
                {t('This week has no questions yet. Practise it from the mastery map to generate some.')}
              </p>
            )}
          </ChecklistStep>
        </ol>

        <button
          type="button"
          onClick={onboarding.dismiss}
          className="mt-1 min-h-[44px] md:min-h-0 text-xs text-text-muted hover:text-text underline underline-offset-2 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          {t('Hide this checklist')}
        </button>
      </section>
    </Card>
  )
}

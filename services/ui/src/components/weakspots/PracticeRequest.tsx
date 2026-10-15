import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Button } from '../ui'
import {
  useRefreshTonightPlan,
  useRequestTargeted,
  useTargetedGeneration,
} from '../../hooks/useWeakSpots'
import { userErrorMessage } from '../../lib/userError'
import { dailyCapMessage, isDailyCapError, isGenerationActive } from '../../lib/weakSpots'
import { AppApiError } from '../../api/errors'
import type { TargetedKind } from '../../types'

interface PracticeRequestProps {
  courseId: string
  week: number
  kind: TargetedKind
  label: string
  variant?: 'primary' | 'secondary'
}

/**
 * One "Practise this week" request: POST, poll until the worker finishes, then
 * offer to refresh tonight's plan. A 202 (new) and a 200 (the one already in
 * flight) are the same body, so both simply start polling that id. The 403
 * consent dialog is handled by the API client, which retries once on agreement.
 */
export function PracticeRequest({ courseId, week, kind, label, variant = 'primary' }: PracticeRequestProps) {
  const { t } = useTranslation()
  const request = useRequestTargeted()
  const refresh = useRefreshTonightPlan()
  const [generationId, setGenerationId] = useState<string | null>(null)
  const generation = useTargetedGeneration(generationId)

  const g = generation.data
  const active = request.isPending || (generationId !== null && (!g || isGenerationActive(g)) && !generation.isError)

  const submit = () => {
    request.mutate(
      { course_id: courseId, week, kind },
      { onSuccess: (created) => setGenerationId(created.id) },
    )
  }

  let error: string | null = null
  if (request.isError) {
    const err = request.error
    if (isDailyCapError(err)) error = dailyCapMessage()
    else if (err instanceof AppApiError && err.code === 'ai_consent_required') {
      error = t('Generating practice needs your OK to use AI. Try again and accept to continue.')
    } else error = userErrorMessage(err, t("Couldn't start practice generation"))
  } else if (generation.isError) {
    error = userErrorMessage(generation.error, t("Couldn't check on the practice generation"))
  } else if (g?.status === 'failed') {
    error = t("Practice generation didn't finish. Try again in a moment.")
  }

  return (
    <div className="space-y-2">
      <Button
        variant={variant}
        size="sm"
        className="min-h-[44px] md:min-h-0"
        onClick={submit}
        loading={request.isPending}
        disabled={active}
      >
        {label}
      </Button>

      <div aria-live="polite" className="text-xs text-text-muted">
        {active && !request.isPending && <p role="status">{t('Generating practice from your weak spots…')}</p>}
        {g?.status === 'completed' && g.created_count > 0 && (
          <div className="space-y-2">
            <p role="status" className="text-sage-fg">
              {t('{{count}} new practice items are ready.', { count: g.created_count })}
            </p>
            {refresh.isSuccess ? (
              <p>
                {t("Tonight's plan is updated.")}{' '}
                <Link to="/" className="underline underline-offset-2">
                  {t('Back to the dashboard')}
                </Link>
              </p>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                className="min-h-[44px] md:min-h-0"
                onClick={() => refresh.mutate()}
                loading={refresh.isPending}
              >
                {t("Refresh tonight's plan")}
              </Button>
            )}
          </div>
        )}
        {g?.status === 'completed' && g.created_count === 0 && (
          <p role="status">{t('Nothing new to add: the candidates repeated what you already have.')}</p>
        )}
      </div>

      {error && (
        <p role="alert" className="text-xs text-red-fg">
          {error}
        </p>
      )}
      {refresh.isError && (
        <p role="alert" className="text-xs text-red-fg">
          {userErrorMessage(refresh.error, t("Couldn't refresh the plan"))}
        </p>
      )}
    </div>
  )
}

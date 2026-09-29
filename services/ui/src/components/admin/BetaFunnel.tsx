import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useBetaFunnel } from '../../hooks/useApi'
import { ErrorState, Skeleton } from '../ui'
import type { BetaFunnel as BetaFunnelData } from '../../types'

interface Step {
  label: string
  value: number
  /** What a drop here actually means, so the number is read correctly. */
  hint: string
}

function steps(data: BetaFunnelData): Step[] {
  return [
    {
      label: 'Invited',
      value: data.invites_issued,
      hint: 'Invite capacity currently outstanding — revoked and expired codes are not counted.',
    },
    {
      label: 'Registered',
      value: data.registered,
      hint: 'Accounts that exist.',
    },
    {
      label: 'Verified',
      value: data.verified,
      hint: 'A drop here is usually SMTP, not disinterest.',
    },
    {
      label: 'Uploaded',
      value: data.uploaded,
      hint: 'The first step that means actually trying the product.',
    },
    {
      label: 'Processed',
      value: data.processed,
      hint: 'A drop from Uploaded is the pipeline failing people — not them losing interest.',
    },
    {
      label: 'Returned',
      value: data.returned,
      hint: 'Active on two or more separate days.',
    },
    {
      label: 'Active 7d',
      value: data.active_7d,
      hint: 'Used the app in the last week.',
    },
  ]
}

/** Percentage of the widest step, for the bar. Avoids dividing by zero. */
function widthPct(value: number, max: number): number {
  return max > 0 ? Math.max((value / max) * 100, value > 0 ? 4 : 0) : 0
}

/**
 * Where invited testers stop.
 *
 * Every number comes from data the app already records, so it is accurate for
 * testers who signed up long before anyone thought to measure them.
 */
export function BetaFunnel() {
  const { t } = useTranslation()

  const [includeAdmins, setIncludeAdmins] = useState(false)
  const { data, isLoading, isError, refetch } = useBetaFunnel(includeAdmins)

  if (isLoading) {
    return (
      <div className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
        <Skeleton height={12} width={120} />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} height={20} />
        ))}
      </div>
    )
  }

  if (isError && !data) {
    return <ErrorState compact title={t("The funnel couldn't load")} onRetry={() => refetch()} />
  }

  if (!data) return null

  const rows = steps(data)
  const max = Math.max(...rows.map((s) => s.value), 1)

  return (
    <section className="bg-surface-1 rounded-xl border border-border p-4 space-y-3">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-text">{t('Beta funnel')}</h2>
          <p className="text-[11px] text-text-faint">
            {t('Derived from existing data — accurate for testers who signed up before this existed.')}
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-[11px] text-text-muted shrink-0">
          <input
            type="checkbox"
            checked={includeAdmins}
            onChange={(e) => setIncludeAdmins(e.target.checked)}
          />
          {t('Include admins')}
        </label>
      </header>

      <ol className="space-y-1.5">
        {rows.map((step) => (
          <li key={step.label} className="flex items-center gap-3" title={t(step.hint)}>
            <span className="w-20 shrink-0 text-[11px] text-text-muted">{t(step.label)}</span>
            <div className="flex-1 h-5 bg-surface-2 rounded overflow-hidden">
              <div
                className="h-full bg-sage/40"
                style={{ width: `${widthPct(step.value, max)}%` }}
              />
            </div>
            <span className="w-10 shrink-0 text-right text-xs tabular-nums text-text">
              {step.value}
            </span>
          </li>
        ))}
      </ol>

      {data.stalled_after_registering > 0 && (
        <p className="text-xs text-text-muted">
          {t('{{count}} account registered without ever uploading.', {
            count: data.stalled_after_registering,
          })}
        </p>
      )}

      {!includeAdmins && data.excluded_admins > 0 && (
        <p className="text-[11px] text-text-faint">
          {data.excluded_demo > 0
            ? t(
                '{{admins}} admin and {{demo}} demo accounts are excluded. Totals here will not match the user count above.',
                { admins: data.excluded_admins, demo: data.excluded_demo },
              )
            : t('{{count}} admin account is excluded. Totals here will not match the user count above.', {
                count: data.excluded_admins,
              })}
        </p>
      )}
    </section>
  )
}

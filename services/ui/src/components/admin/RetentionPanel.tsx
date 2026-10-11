import { useTranslation } from 'react-i18next'
import { useAdminRetention } from '../../hooks/useApi'
import { ErrorState, Skeleton } from '../ui'
import type { RetentionFeatureWeek } from '../../types'

const WEEKS = 8
const MISSING = '—'

function day(value: number | null, signups: number): string {
  if (value === null) return MISSING
  return signups > 0 ? `${value} (${Math.round((value / signups) * 100)}%)` : String(value)
}

/** Weekly actives grouped by feature event, oldest week first. */
function byEvent(features: RetentionFeatureWeek[]): [string, RetentionFeatureWeek[]][] {
  const groups = new Map<string, RetentionFeatureWeek[]>()
  for (const f of features) groups.set(f.event, [...(groups.get(f.event) ?? []), f])
  return [...groups.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([event, rows]) => [event, rows.sort((a, b) => a.week_start.localeCompare(b.week_start))])
}

/** Read-only retention: signup cohorts by D1/D7/D30 and weekly active users per feature (services.usage v1). */
export function RetentionPanel() {
  const { t } = useTranslation()
  const { data, isLoading, isError, refetch } = useAdminRetention(WEEKS)

  if (isLoading) {
    return (
      <div className="bg-surface-1 rounded-xl border border-border p-4 space-y-3" aria-busy="true">
        <Skeleton height={12} width={120} />
        <Skeleton height={64} />
      </div>
    )
  }

  if (isError && !data) {
    return <ErrorState compact title={t("Retention couldn't load")} onRetry={() => refetch()} />
  }

  if (!data) return null

  const empty = data.cohorts.length === 0 && data.features.length === 0

  return (
    <section className="bg-surface-1 rounded-xl border border-border p-4 space-y-4">
      <header>
        <h2 className="text-sm font-medium text-text">{t('Retention')}</h2>
        <p className="text-[11px] text-text-faint">
          {t('Signup cohorts by ISO week. A dash means the cohort has not reached that day yet. Admin and demo accounts are excluded.')}
        </p>
      </header>

      {empty ? (
        <p className="text-xs text-text-muted">{t('No usage data in this period yet.')}</p>
      ) : (
        <>
          {data.cohorts.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <caption className="sr-only">{t('Retention by signup week')}</caption>
                <thead>
                  <tr className="text-left text-text-muted">
                    <th scope="col" className="py-1 pr-2 font-medium">{t('Week of')}</th>
                    <th scope="col" className="py-1 pr-2 font-medium text-right">{t('Signups')}</th>
                    <th scope="col" className="py-1 pr-2 font-medium text-right">{t('D1')}</th>
                    <th scope="col" className="py-1 pr-2 font-medium text-right">{t('D7')}</th>
                    <th scope="col" className="py-1 font-medium text-right">{t('D30')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {data.cohorts.map((c) => (
                    <tr key={c.week_start} className="tabular-nums text-text">
                      <th scope="row" className="py-1.5 pr-2 text-left font-normal">{c.week_start}</th>
                      <td className="py-1.5 pr-2 text-right">{c.signups}</td>
                      <td className="py-1.5 pr-2 text-right">{day(c.d1, c.signups)}</td>
                      <td className="py-1.5 pr-2 text-right">{day(c.d7, c.signups)}</td>
                      <td className="py-1.5 text-right">{day(c.d30, c.signups)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {data.features.length > 0 && (
            <div>
              <h3 className="text-[11px] font-medium text-text-muted mb-1.5">{t('Weekly active users per feature')}</h3>
              <ul className="space-y-2">
                {byEvent(data.features).map(([event, rows]) => (
                  <li key={event}>
                    <p className="font-mono text-xs text-text">{event}</p>
                    <ul className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-text-muted tabular-nums">
                      {rows.map((r) => (
                        <li key={r.week_start}>
                          {r.week_start.slice(5)}: <span className="text-text">{r.active_users}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  )
}

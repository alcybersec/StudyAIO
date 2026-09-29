import { Card } from '../ui'
import i18n from '../../i18n'
import { useTranslation } from 'react-i18next'
import { useBillingOverview, useCheckout, usePortal } from '../../hooks/useBilling'
import { usePlan } from '../../hooks/usePlan'

function UsageBar({ current, limit, label }: { current: number; limit: number | null; label: string }) {
  const { t } = useTranslation()

  if (limit === null) {
    return (
      <div className="flex items-center justify-between text-sm">
        <span className="text-text-muted">{label}</span>
        <span className="text-text font-medium">{t('{{count}} used', { count: current })}</span>
      </div>
    )
  }

  const pct = Math.min(100, (current / limit) * 100)
  const isNearLimit = pct >= 80

  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-text-muted">{label}</span>
        <span className={`font-medium ${isNearLimit ? 'text-amber-fg' : 'text-text'}`}>
          {current} / {limit}
        </span>
      </div>
      <div className="h-2 bg-surface-0 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            isNearLimit ? 'bg-amber' : 'bg-sage'
          }`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function BillingSection() {
  const { t } = useTranslation()

  const { isSelfHosted, isPro, canUpgrade } = usePlan()
  const { data: billing, isLoading } = useBillingOverview()
  const checkout = useCheckout()
  const portal = usePortal()

  if (isSelfHosted) {
    return (
      <Card>
        <h2 className="text-lg font-semibold text-text mb-4">{t('Plan & Billing')}</h2>
        <p className="text-sm text-text-muted">
          {t("You're running StudyAIO in self-hosted mode. All features are unlocked with no usage limits.")}
        </p>
      </Card>
    )
  }

  if (isLoading || !billing) {
    return (
      <Card>
        <h2 className="text-lg font-semibold text-text mb-4">{t('Plan & Billing')}</h2>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-surface-0 rounded w-1/3" />
          <div className="h-2 bg-surface-0 rounded" />
          <div className="h-2 bg-surface-0 rounded" />
        </div>
      </Card>
    )
  }

  const { subscription, usage } = billing

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-text">{t('Plan & Billing')}</h2>
        <span
          className={`px-2.5 py-1 text-xs font-bold uppercase rounded-full ${
            isPro
              ? 'bg-amber-soft text-amber-fg'
              : 'bg-surface-0 text-text-muted'
          }`}
        >
          {subscription.plan}
        </span>
      </div>

      {/* Usage meters */}
      <div className="space-y-4 mb-6">
        <UsageBar
          current={usage.ai_calls_today}
          limit={usage.ai_calls_limit}
          label={t('AI calls today')}
        />
        <UsageBar
          current={usage.uploads_this_month}
          limit={usage.uploads_limit}
          label={t('Uploads this month')}
        />
        <UsageBar
          current={usage.courses_count}
          limit={usage.courses_limit}
          label={t('Courses')}
        />
      </div>

      {/* Subscription period */}
      {subscription.current_period_end && (
        <p className="text-xs text-text-muted mb-4">
          {subscription.cancel_at_period_end
            ? t('Cancels on {{date}}', {
                date: new Date(subscription.current_period_end).toLocaleDateString(i18n.language),
              })
            : t('Renews on {{date}}', {
                date: new Date(subscription.current_period_end).toLocaleDateString(i18n.language),
              })}
        </p>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        {canUpgrade && (
          <button
            type="button"
            onClick={() => checkout.mutate()}
            disabled={checkout.isPending}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-sage text-on-accent hover:bg-sage-hover disabled:opacity-50 transition-colors"
          >
            {checkout.isPending ? t('Loading...') : t('Upgrade to Pro')}
          </button>
        )}
        {isPro && (
          <button
            type="button"
            onClick={() => portal.mutate()}
            disabled={portal.isPending}
            className="px-4 py-2 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface-2 disabled:opacity-50 transition-colors"
          >
            {portal.isPending ? t('Loading...') : t('Manage Subscription')}
          </button>
        )}
      </div>
    </Card>
  )
}

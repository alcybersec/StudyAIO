import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import i18n from '../../../i18n'
import { Card, Skeleton, Switch } from '../../ui'
import { useSettings, useUpdateSettings } from '../../../hooks/useApi'

/**
 * Leaderboard visibility. Opt-in: nobody appears to others until they turn
 * this on. The caller still sees their own XP and level either way.
 */
export function LeaderboardPrivacyCard() {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useSettings()
  const update = useUpdateSettings()

  const optedIn = data?.leaderboard_opt_in === true

  return (
    <Card>
      <h2 className="text-[13px] font-semibold text-text mb-2">{t('Leaderboard')}</h2>
      <div className="max-w-md space-y-2">
        {isLoading ? (
          <Skeleton height={20} width={220} />
        ) : isError || !data ? (
          <p role="alert" className="text-xs text-red-fg">
            {t("Couldn't load your leaderboard setting.")}
          </p>
        ) : (
          <Switch
            id="leaderboard-opt-in"
            label={t('Show me on the leaderboard')}
            checked={optedIn}
            disabled={update.isPending}
            onCheckedChange={(checked) =>
              update.mutate(
                { leaderboard_opt_in: checked },
                {
                  onError: () =>
                    toast.error(i18n.t("Couldn't update your leaderboard setting. Please try again.")),
                },
              )
            }
          />
        )}
        <p className="text-xs text-text-muted">
          {t('Off by default. When off, other users cannot see you on the leaderboard; you still see your own XP and level.')}
        </p>
        {update.isPending && (
          <p role="status" className="text-xs text-text-faint">
            {t('Saving...')}
          </p>
        )}
      </div>
    </Card>
  )
}
